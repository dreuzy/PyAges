import hashlib
import json
import zipfile
from pathlib import Path

import yaml

from scripts import build_zenodo_bundle


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _core_archive(tmp_path: Path, workbook: Path, xll: Path) -> Path:
    archive = tmp_path / "core"
    (archive / "campaign/tracerlpm").mkdir(parents=True)
    (archive / "campaign/article_package/provenance").mkdir(parents=True)
    (archive / "source").mkdir()
    config = {
        "workbook_sha256": _digest(workbook),
        "xll_sha256": _digest(xll),
        "timeout_seconds": 180,
        "reuse_excel_session": True,
    }
    (archive / "campaign/tracerlpm/runner-config.yaml").write_text(
        yaml.safe_dump(config), encoding="utf-8"
    )
    summary = {
        "forward_verification": {"case_count": 1, "status": "measured"},
        "pyage_tracerlpm": {
            "paired_cases": 1,
            "pyage_successful": 1,
            "tracerlpm_successful": 1,
        },
        "shifted_exponential": {
            "groups": 1,
            "max_split_rhat": 1.0,
            "min_ess": 500.0,
        },
        "holten_h4": {"groups": 1, "max_split_rhat": 1.0, "min_ess": 500.0},
        "ploemeur_shifted_exponential": {
            "groups": 1,
            "max_split_rhat": 1.0,
            "min_ess": 500.0,
        },
        "ploemeur_physical_ig": {
            "posterior_sets": 1,
            "max_split_rhat": 1.0,
            "min_bulk_ess": 500.0,
            "min_tail_ess": 500.0,
        },
    }
    (
        archive / "campaign/article_package/provenance/article_package_manifest.json"
    ).write_text(json.dumps({"scientific_summary": summary}), encoding="utf-8")
    with zipfile.ZipFile(archive / "source/pyage-source.zip", "w") as source:
        source.writestr(
            "CITATION.cff",
            yaml.safe_dump(
                {
                    "title": "PyAge",
                    "version": "test-version",
                    "authors": [{"family-names": "Researcher", "given-names": "Test"}],
                    "repository-code": "https://example.test/pyage",
                }
            ),
        )
        source.writestr("LICENSE", "test license\n")
        source.writestr("NOTICE-DATA.md", "test data notice\n")
    files = []
    for path in sorted(archive.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(archive).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _digest(path),
                }
            )
    (archive / "ARCHIVE_MANIFEST.json").write_text(
        json.dumps({"git_head": "test-head", "files": files}), encoding="utf-8"
    )
    (archive / "CHECKSUMS.sha256").write_text(
        "\n".join(f"{item['sha256']}  {item['path']}" for item in files) + "\n",
        encoding="ascii",
    )
    return archive


def test_build_zenodo_bundle_adds_readable_metadata_and_exact_dependencies(tmp_path):
    workbook = tmp_path / "TracerLPM.xlsm"
    xll = tmp_path / "TracerLPM.xll"
    workbook.write_bytes(b"workbook")
    xll.write_bytes(b"add-in")
    archive = _core_archive(tmp_path, workbook, xll)
    output = tmp_path / "pyage-zenodo"
    zip_output = tmp_path / "pyage-zenodo.zip"

    build_zenodo_bundle.build_bundle(
        archive,
        output,
        zip_output,
        workbook=workbook,
        xll=xll,
        title="PyAge test archive",
        doi="10.5281/zenodo.test",
    )

    manifest = build_zenodo_bundle.validate_bundle(output)
    assert (output / "README.md").is_file()
    assert (output / "LICENSE").read_text(encoding="utf-8") == "test license\n"
    assert (output / "external/tracerlpm/TracerLPM.xlsm").read_bytes() == b"workbook"
    assert manifest["doi"] == "10.5281/zenodo.test"
    assert len(manifest["external_dependencies"]) == 2
    assert build_zenodo_bundle.validate_zip(output, zip_output) > 0


def test_tracerlpm_dependency_hash_is_mandatory(tmp_path):
    dependency = tmp_path / "dependency.bin"
    dependency.write_bytes(b"wrong")

    try:
        build_zenodo_bundle._verify_tracerlpm_dependency(
            dependency, hashlib.sha256(b"expected").hexdigest(), "test"
        )
    except RuntimeError as error:
        assert "SHA-256 mismatch" in str(error)
    else:
        raise AssertionError("mismatching dependency was accepted")
