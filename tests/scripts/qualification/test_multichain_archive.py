# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Fast contracts for the generic multi-chain qualification archive."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from pyages import __version__
from scripts.qualification import build_multichain_archive as archive


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualified_result(root: Path, config: Path) -> Path:
    method = root / "Metropolis_Hastings"
    (method / "chains/chain_001").mkdir(parents=True)
    (method / "chains/chain_002").mkdir(parents=True)
    files = {
        method / "mcmc_diagnostics.tsv": (
            "parameter\trhat\tbulk_ess\ttail_ess\tqualified\t"
            "included_in_qualification\n"
            "mu\t1.001\t400\t350\tTrue\tTrue\n"
        ),
        method / "results_calibration.txt": (
            "qualification_status\tqualified\npooling_written\tTrue\n"
        ),
        method / "ensemble_provenance.txt": (
            "execution_mode\tmulti_chain\nqualification_status\tqualified\n"
        ),
        method / "chains/chain_001/lpm_dist_calibrated.txt": "mu\n1.0\n",
        method / "chains/chain_002/lpm_dist_calibrated.txt": "mu\n2.0\n",
        method / "lpm_dist_calibrated.txt": "mu\n1.0\n2.0\n",
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    artifacts = {path.relative_to(root).as_posix(): _sha256(path) for path in files}
    manifest = {
        "schema_version": 2,
        "status": "complete",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "workflow": "single_date",
        "pyages_version": __version__,
        "configuration": {"path": config.name, "sha256": _sha256(config)},
        "package": {"name": "PyAges", "version": __version__},
        "repository": {"git_head": "b" * 40, "dirty": False},
        "artifacts_sha256": artifacts,
    }
    (root / "result_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return root


def _distributions(root: Path) -> tuple[Path, Path]:
    wheel = root / f"pyages-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as output:
        output.writestr(
            f"pyages-{__version__}.dist-info/METADATA",
            f"Name: PyAges\nVersion: {__version__}\n",
        )
    sdist = root / f"pyages-{__version__}.tar.gz"
    metadata = f"Name: PyAges\nVersion: {__version__}\n".encode()
    with tarfile.open(sdist, "w:gz") as output:
        for relative in (
            "PKG-INFO",
            "pyages.egg-info/PKG-INFO",
        ):
            info = tarfile.TarInfo(f"pyages-{__version__}/{relative}")
            info.size = len(metadata)
            info.mtime = 0
            output.addfile(info, io.BytesIO(metadata))
    return wheel, sdist


def test_sdist_rejects_inconsistent_duplicate_metadata(tmp_path: Path) -> None:
    sdist = tmp_path / "inconsistent.tar.gz"
    payloads = (
        ("package/PKG-INFO", b"Name: PyAges\nVersion: 1.0\n"),
        ("package/pyages.egg-info/PKG-INFO", b"Name: PyAges\nVersion: 2.0\n"),
    )
    with tarfile.open(sdist, "w:gz") as output:
        for name, metadata in payloads:
            info = tarfile.TarInfo(name)
            info.size = len(metadata)
            info.mtime = 0
            output.addfile(info, io.BytesIO(metadata))

    with pytest.raises(RuntimeError, match="inconsistent PKG-INFO metadata"):
        archive._distribution_identity(sdist)


@pytest.fixture
def deterministic_runtime(monkeypatch):
    def git_text(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args[:2] == ("status", "--porcelain=v1"):
            return "?? draft-only.txt"
        if args == ("tag", "--points-at", "HEAD"):
            return ""
        if args[:2] == ("cat-file", "-t"):
            return "tag"
        if args == ("ls-files", "--others", "--exclude-standard"):
            return "draft-only.txt"
        raise AssertionError(args)

    monkeypatch.setattr(archive, "_git_text", git_text)
    monkeypatch.setattr(archive, "_git_bytes", lambda *unused: b"tracked diff\n")
    monkeypatch.setattr(
        archive,
        "_write_git_archive",
        lambda destination, unused_head: destination.write_bytes(b"git archive\n"),
    )

    def environment(destination: Path, extra_files) -> list[str]:
        destination.mkdir(parents=True)
        (destination / "pip-freeze.txt").write_text("PyAges==test\n", encoding="utf-8")
        (destination / "runtime.json").write_text("{}\n", encoding="utf-8")
        assert not tuple(extra_files)
        return ["environment/pip-freeze.txt", "environment/runtime.json"]

    monkeypatch.setattr(archive, "_write_environment", environment)


def _clean_publication_git(*args: str) -> str:
    if args == ("rev-parse", "HEAD"):
        return "b" * 40
    if args[:2] == ("status", "--porcelain=v1"):
        return ""
    if args == ("tag", "--points-at", "HEAD"):
        return __version__
    if args[:2] == ("cat-file", "-t"):
        return "tag"
    if args == ("ls-files", "--others", "--exclude-standard"):
        return ""
    raise AssertionError(args)


def _inputs(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = tmp_path / "qualification.yaml"
    test = tmp_path / "test_qualification.py"
    report = tmp_path / "qualification.md"
    config.write_text("qualification: true\n", encoding="utf-8")
    test.write_text("def test_qualification(): pass\n", encoding="utf-8")
    report.write_text("# Qualification\n", encoding="utf-8")
    result = _qualified_result(tmp_path / "result", config)
    wheel, sdist = _distributions(tmp_path)
    return {
        "results": [result],
        "yaml_files": [config],
        "test_files": [test],
        "reports": [report],
        "distributions": [wheel, sdist],
    }


def test_draft_archive_is_reproducible_and_self_verifying(
    tmp_path: Path, deterministic_runtime
) -> None:
    inputs = _inputs(tmp_path)
    config = inputs["yaml_files"][0]
    inputs["results"].append(_qualified_result(tmp_path / "second-result", config))
    first = archive.build_archive(**inputs, output=tmp_path / "first.zip", mode="draft")
    second = archive.build_archive(
        **inputs, output=tmp_path / "second.zip", mode="draft"
    )

    assert first.read_bytes() == second.read_bytes()
    payload = archive.verify_archive(first)
    assert payload["publication"]["mode"] == "draft"
    assert not payload["publication"]["publishable"]
    assert payload["publication"]["blockers"] == [
        "Git worktree is dirty",
        "No expected release tag was supplied",
    ]
    assert len(payload["results"]) == 2
    assert {record["kind"] for record in payload["distributions"]} == {
        "wheel",
        "sdist",
    }
    with zipfile.ZipFile(first) as zipped:
        assert "DRAFT — NOT PUBLISHABLE" in zipped.read("README.md").decode()
        assert "not an origin signature" in zipped.read("README.md").decode()
        assert "protocol/yaml/001-qualification.yaml" in zipped.namelist()
        assert "protocol/tests/001-test_qualification.py" in zipped.namelist()
        assert "protocol/reports/001-qualification.md" in zipped.namelist()


def test_publishable_mode_requires_clean_annotated_matching_tag(
    tmp_path: Path, deterministic_runtime, monkeypatch
) -> None:
    inputs = _inputs(tmp_path)
    with pytest.raises(RuntimeError, match="worktree is dirty"):
        archive._publication_state("publishable", __version__)

    monkeypatch.setattr(archive, "_git_text", _clean_publication_git)
    monkeypatch.setattr(archive, "_git_bytes", lambda *unused: b"")
    output = archive.build_archive(
        **inputs,
        output=tmp_path / "publishable.zip",
        mode="publishable",
        expected_tag=__version__,
    )
    payload = archive.verify_archive(output)
    assert payload["publication"]["publishable"]
    assert payload["publication"]["blockers"] == []

    with pytest.raises(RuntimeError, match="does not identify version"):
        archive._publication_state("publishable", "v0.0.0")


@pytest.mark.parametrize(
    ("repository_update", "message"),
    [
        ({"git_head": "c" * 40}, "tagged Git commit"),
        ({"dirty": True}, "dirty or unknown worktree"),
    ],
)
def test_publishable_results_are_bound_to_the_clean_tagged_head(
    tmp_path: Path,
    deterministic_runtime,
    monkeypatch,
    repository_update: dict[str, object],
    message: str,
) -> None:
    inputs = _inputs(tmp_path)
    result = inputs["results"][0]
    manifest_path = result / "result_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["repository"].update(repository_update)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(archive, "_git_text", _clean_publication_git)

    with pytest.raises(RuntimeError, match=message):
        archive.build_archive(
            **inputs,
            output=tmp_path / "provenance-mismatch.zip",
            mode="publishable",
            expected_tag=__version__,
        )


def test_publishable_output_must_be_outside_the_source_repository(
    tmp_path: Path, deterministic_runtime, monkeypatch
) -> None:
    repository = tmp_path / "checkout"
    repository.mkdir()
    inputs = _inputs(tmp_path / "inputs")
    monkeypatch.setattr(archive, "ROOT", repository)

    with pytest.raises(ValueError, match="outside the source repository"):
        archive.build_archive(
            **inputs,
            output=repository / "qualification.zip",
            mode="publishable",
            expected_tag=__version__,
        )


def test_publishable_state_is_rechecked_before_zip_sealing(
    tmp_path: Path, deterministic_runtime, monkeypatch
) -> None:
    inputs = _inputs(tmp_path)
    status_calls = 0

    def changing_git(*args: str) -> str:
        nonlocal status_calls
        if args[:2] == ("status", "--porcelain=v1"):
            status_calls += 1
            return "" if status_calls == 1 else "?? changed-during-build.txt"
        return _clean_publication_git(*args)

    monkeypatch.setattr(archive, "_git_text", changing_git)
    output = tmp_path / "changed-state.zip"
    with pytest.raises(RuntimeError, match="worktree is dirty"):
        archive.build_archive(
            **inputs,
            output=output,
            mode="publishable",
            expected_tag=__version__,
        )
    assert status_calls == 2
    assert not output.exists()
    assert not output.with_name(f"{output.name}.sha256").exists()


@pytest.mark.parametrize(
    "value",
    [
        "protocol/yaml/../outside.yaml",
        "protocol/yaml/C:/outside.yaml",
        r"protocol/yaml/C:\outside.yaml",
        r"protocol\yaml\outside.yaml",
        r"protocol/yaml/\\server\share\outside.yaml",
    ],
)
def test_semantic_paths_reject_posix_and_windows_escapes(
    tmp_path: Path, value: str
) -> None:
    with pytest.raises(RuntimeError, match="Unsafe qualification archive"):
        archive._contained_path(tmp_path, value, "protocol")


def test_zip_members_reject_windows_separators() -> None:
    member = zipfile.ZipInfo("safe")
    member.filename = r"protocol\yaml\outside.yaml"

    class UnsafeArchive:
        def namelist(self) -> list[str]:
            return [member.filename]

        def infolist(self) -> list[zipfile.ZipInfo]:
            return [member]

    with pytest.raises(RuntimeError, match="Unsafe qualification archive member"):
        archive._safe_member_names(UnsafeArchive())


def test_result_hash_and_qualification_are_checked_before_copying(
    tmp_path: Path, deterministic_runtime
) -> None:
    inputs = _inputs(tmp_path)
    result = inputs["results"][0]
    chain = result / "Metropolis_Hastings/chains/chain_001/lpm_dist_calibrated.txt"
    chain.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed="):
        archive.build_archive(**inputs, output=tmp_path / "changed.zip", mode="draft")

    inputs = _inputs(tmp_path / "unqualified")
    result = inputs["results"][0]
    results = result / "Metropolis_Hastings/results_calibration.txt"
    results.write_text(
        "qualification_status\tnot_qualified\npooling_written\tTrue\n",
        encoding="utf-8",
    )
    manifest_path = result / "result_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = results.relative_to(result).as_posix()
    manifest["artifacts_sha256"][relative] = _sha256(results)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="not qualified"):
        archive.build_archive(
            **inputs, output=tmp_path / "unqualified.zip", mode="draft"
        )


def test_archive_sidecar_and_supplied_configuration_are_mandatory(
    tmp_path: Path, deterministic_runtime
) -> None:
    inputs = _inputs(tmp_path)
    wrong_yaml = tmp_path / "wrong.yaml"
    wrong_yaml.write_text("different: true\n", encoding="utf-8")
    inputs["yaml_files"] = [wrong_yaml]
    with pytest.raises(RuntimeError, match="configuration digest"):
        archive.build_archive(
            **inputs, output=tmp_path / "wrong-config.zip", mode="draft"
        )

    inputs = _inputs(tmp_path / "sidecar")
    output = archive.build_archive(
        **inputs, output=tmp_path / "sidecar.zip", mode="draft"
    )
    output.with_name(f"{output.name}.sha256").write_text(
        f"{'0' * 64}  {output.name}\n", encoding="ascii"
    )
    with pytest.raises(RuntimeError, match="sidecar is invalid"):
        archive.verify_archive(output)


def test_verifier_rejects_a_repacked_changed_member(
    tmp_path: Path, deterministic_runtime
) -> None:
    inputs = _inputs(tmp_path)
    output = archive.build_archive(
        **inputs, output=tmp_path / "changed-member.zip", mode="draft"
    )
    with zipfile.ZipFile(output) as source:
        members = {name: source.read(name) for name in source.namelist()}
    members["README.md"] += b"changed\n"
    with zipfile.ZipFile(output, "w") as changed:
        for name, data in members.items():
            changed.writestr(name, data)
    output.with_name(f"{output.name}.sha256").write_text(
        f"{_sha256(output)}  {output.name}\n", encoding="ascii"
    )

    with pytest.raises(RuntimeError, match="member changed"):
        archive.verify_archive(output)
