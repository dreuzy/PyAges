# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Discovery and orchestration contracts for the extensive CI archive."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from pyages import __version__
from scripts.qualification import build_ci_multichain_archive as ci_archive


def _write_manifest(root: Path, digest: str, *, qualified: bool = True) -> Path:
    root.mkdir(parents=True)
    manifest = root / "result_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "configuration": {"sha256": digest},
                "qualified_test_fixture": qualified,
                "run_id": root.name,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def _populate_basetemp(root: Path) -> dict[str, tuple[Path, Path, str]]:
    populated: dict[str, tuple[Path, Path, str]] = {}
    for index, case in enumerate(ci_archive.CASES):
        test_temp = root / f"test_{case.key}{index}"
        test_temp.mkdir(parents=True)
        executed_yaml = test_temp / case.executed_yaml_name
        executed_yaml.write_text(f"case: {case.key}\n", encoding="utf-8")
        digest = ci_archive.build_multichain_archive.sha256(executed_yaml)
        result = test_temp / f"{case.key}-qualified"
        _write_manifest(result, digest)
        populated[case.key] = (executed_yaml, result, digest)
    unrelated = root / "test_unrelated0/unqualified"
    _write_manifest(unrelated, "f" * 64, qualified=False)
    return populated


@pytest.fixture
def fake_result_validation(monkeypatch):
    def validate(root: Path) -> dict[str, object]:
        payload = json.loads(
            (root / "result_manifest.json").read_text(encoding="utf-8")
        )
        if not payload.get("qualified_test_fixture"):
            raise RuntimeError("not a qualified fixture")
        digest = payload["configuration"]["sha256"]
        return {
            "workflow": "single_date",
            "run_id": payload["run_id"],
            "configuration_sha256": digest,
            "package_version": __version__,
            "repository_git_head": None,
            "repository_dirty": None,
            "qualified_directories": ["Metropolis_Hastings"],
            "artifact_count": 1,
            "manifest_sha256": "a" * 64,
        }

    monkeypatch.setattr(
        ci_archive.build_multichain_archive, "_validate_result_tree", validate
    )


def _distributions(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    wheel = root / f"pyages-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as output:
        output.writestr(
            f"pyages-{__version__}.dist-info/METADATA",
            f"Name: PyAges\nVersion: {__version__}\n",
        )
    sdist = root / f"pyages-{__version__}.tar.gz"
    metadata = f"Name: PyAges\nVersion: {__version__}\n".encode()
    with tarfile.open(sdist, "w:gz") as output:
        info = tarfile.TarInfo(f"pyages-{__version__}/PKG-INFO")
        info.size = len(metadata)
        info.mtime = 0
        output.addfile(info, io.BytesIO(metadata))
    return wheel, sdist


def test_discovery_matches_exactly_four_results_to_executed_yaml_hashes(
    tmp_path: Path, fake_result_validation
) -> None:
    populated = _populate_basetemp(tmp_path)

    discovered = ci_archive.discover_qualifications(tmp_path)

    assert [item.case for item in discovered] == list(ci_archive.CASES)
    assert len(discovered) == 4
    for item in discovered:
        yaml, result, digest = populated[item.case.key]
        assert item.executed_yaml == yaml.resolve()
        assert item.result == result.resolve()
        assert item.configuration_sha256 == digest


def test_discovery_rejects_duplicate_yaml_and_unexpected_qualified_result(
    tmp_path: Path, fake_result_validation
) -> None:
    populated = _populate_basetemp(tmp_path)
    first_case = ci_archive.CASES[0]
    original = populated[first_case.key][0]
    duplicate = original.parent / "duplicate" / first_case.executed_yaml_name
    duplicate.parent.mkdir()
    duplicate.write_bytes(original.read_bytes())
    with pytest.raises(RuntimeError, match="exactly one executed YAML"):
        ci_archive.discover_qualifications(tmp_path)

    duplicate.unlink()
    extra_yaml_digest = "e" * 64
    extra_owner = tmp_path / "test_extra0"
    extra_owner.mkdir()
    (extra_owner / first_case.executed_yaml_name).write_text(
        "unmatched: true\n", encoding="utf-8"
    )
    _write_manifest(extra_owner / "extra-qualified", extra_yaml_digest)
    with pytest.raises(RuntimeError, match="Unexpected qualified result manifests"):
        ci_archive.discover_qualifications(tmp_path)

    assert populated  # keep the four canonical fixtures present throughout


def test_discovery_rejects_an_invalid_expected_result(
    tmp_path: Path, fake_result_validation
) -> None:
    populated = _populate_basetemp(tmp_path)
    result = populated[ci_archive.CASES[2].key][1]
    payload = json.loads((result / "result_manifest.json").read_text(encoding="utf-8"))
    payload["qualified_test_fixture"] = False
    (result / "result_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="exactly one qualified result .* found 0"):
        ci_archive.discover_qualifications(tmp_path)


def test_discovery_ignores_invalid_yaml_fixtures_from_other_pytest_cases(
    tmp_path: Path, fake_result_validation
) -> None:
    populated = _populate_basetemp(tmp_path)
    noise = tmp_path / "test_archive_unit_noise0"
    noise.mkdir()
    for case in ci_archive.CASES:
        executed_yaml = noise / case.executed_yaml_name
        executed_yaml.write_text(f"fixture: {case.key}\n", encoding="utf-8")
        digest = ci_archive.build_multichain_archive.sha256(executed_yaml)
        _write_manifest(noise / f"{case.key}-invalid", digest, qualified=False)
    _write_manifest(
        tmp_path / "test_generic_archive_fixture0/qualified-result",
        "d" * 64,
        qualified=True,
    )

    discovered = ci_archive.discover_qualifications(tmp_path)

    assert [item.case for item in discovered] == list(ci_archive.CASES)
    assert populated


def test_ci_wrapper_passes_only_canonical_inputs_to_draft_builder(
    tmp_path: Path, fake_result_validation, monkeypatch
) -> None:
    populated = _populate_basetemp(tmp_path / "pytest")
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "pyages-test-py3-none-any.whl"
    sdist = dist / "pyages-test.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    captured: dict[str, object] = {}

    def build_archive(**kwargs):
        captured.update(kwargs)
        return Path(kwargs["output"])

    monkeypatch.setattr(
        ci_archive.build_multichain_archive, "build_archive", build_archive
    )
    output = tmp_path / "qualification.zip"

    assert (
        ci_archive.build_ci_archive(
            basetemp=tmp_path / "pytest", dist_dir=dist, output=output
        )
        == output
    )
    assert captured["mode"] == "draft"
    assert captured["expected_tag"] is None
    assert captured["output"] == output
    assert captured["results"] == [
        populated[case.key][1].resolve() for case in ci_archive.CASES
    ]
    assert captured["yaml_files"] == [
        populated[case.key][0].resolve() for case in ci_archive.CASES
    ]
    assert captured["test_files"] == tuple(
        case.test.resolve() for case in ci_archive.CASES
    )
    assert captured["reports"] == tuple(
        case.report.resolve() for case in ci_archive.CASES
    )
    assert captured["distributions"] == (wheel.resolve(), sdist.resolve())


def test_canonical_wrapper_forwards_publishable_mode_and_expected_tag(
    tmp_path: Path, fake_result_validation, monkeypatch
) -> None:
    _populate_basetemp(tmp_path / "pytest")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "pyages-test-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "pyages-test.tar.gz").write_bytes(b"sdist")
    captured: dict[str, object] = {}

    def build_archive(**kwargs):
        captured.update(kwargs)
        return Path(kwargs["output"])

    monkeypatch.setattr(
        ci_archive.build_multichain_archive, "build_archive", build_archive
    )
    output = tmp_path / "qualification.zip"
    ci_archive.build_ci_archive(
        basetemp=tmp_path / "pytest",
        dist_dir=dist,
        output=output,
        mode="publishable",
        expected_tag="1.2.3",
    )

    assert captured["mode"] == "publishable"
    assert captured["expected_tag"] == "1.2.3"
    assert len(captured["results"]) == len(ci_archive.CASES) == 4


def test_canonical_publishable_wrapper_requires_expected_tag(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires --expected-tag"):
        ci_archive.build_ci_archive(
            basetemp=tmp_path,
            dist_dir=tmp_path,
            output=tmp_path / "qualification.zip",
            mode="publishable",
        )


def test_canonical_wrapper_builds_and_verifies_one_archive_with_four_cases(
    tmp_path: Path, fake_result_validation, monkeypatch
) -> None:
    basetemp = tmp_path / "pytest"
    populated = _populate_basetemp(basetemp)
    dist = tmp_path / "dist"
    _distributions(dist)
    generic = ci_archive.build_multichain_archive

    def git_text(*args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args[:2] == ("status", "--porcelain=v1"):
            return "?? local-review.txt"
        if args == ("tag", "--points-at", "HEAD"):
            return ""
        if args == ("ls-files", "--others", "--exclude-standard"):
            return "local-review.txt"
        raise AssertionError(args)

    monkeypatch.setattr(generic, "_git_text", git_text)
    monkeypatch.setattr(generic, "_git_bytes", lambda *unused: b"tracked diff\n")
    monkeypatch.setattr(
        generic,
        "_write_git_archive",
        lambda destination, unused_head: destination.write_bytes(b"git archive\n"),
    )

    def environment(destination: Path, extra_files) -> list[str]:
        destination.mkdir(parents=True)
        (destination / "pip-freeze.txt").write_text("PyAges==test\n", encoding="utf-8")
        (destination / "runtime.json").write_text("{}\n", encoding="utf-8")
        assert not tuple(extra_files)
        return ["environment/pip-freeze.txt", "environment/runtime.json"]

    monkeypatch.setattr(generic, "_write_environment", environment)
    output = ci_archive.build_ci_archive(
        basetemp=basetemp,
        dist_dir=dist,
        output=tmp_path / "qualification.zip",
    )

    manifest = generic.verify_archive(output)
    assert len(manifest["results"]) == len(ci_archive.CASES) == 4
    assert {record["configuration_sha256"] for record in manifest["results"]} == {
        value[2] for value in populated.values()
    }
    assert manifest["publication"]["mode"] == "draft"


def test_extensive_workflow_builds_archive_before_always_upload() -> None:
    workflow = (ci_archive.ROOT / ".github/workflows/extensive-tests.yml").read_text(
        encoding="utf-8"
    )
    pytest_position = workflow.index("python -m pytest -q --run-extensive")
    wrapper_position = workflow.index(
        "python -m scripts.qualification.build_ci_multichain_archive"
    )
    upload_position = workflow.index("Preserve multi-chain scientific evidence")

    assert pytest_position < wrapper_position < upload_position
    assert "RUNNER_TEMP" in workflow
    assert "GITHUB_RUN_ID" in workflow
    assert "runner.temp" in workflow
    assert '--basetemp "$RUNNER_TEMP/pyages-extensive-$GITHUB_RUN_ID"' in workflow
    assert ".artifacts/extensive-pytest" not in workflow
    assert "--dist-dir dist" in workflow
    assert ".artifacts/multichain-qualification-draft.zip" in workflow
    assert ".artifacts/multichain-qualification-draft.zip.sha256" in workflow
    for case in ci_archive.CASES:
        assert case.executed_yaml_name in workflow
    assert "test_synthetic_example_multich*" not in workflow
    assert "test_ploemeur_f09_multichain_s*" not in workflow
    assert "test_ploemeur_ig_shifted_prior*" not in workflow
    assert "test_ploemeur_temporal_multich*" not in workflow
    for scientific_path in (
        "pyages/**",
        "examples/**/*.py",
        "examples/**/*.yaml",
        "examples/**/*.csv",
        "examples/**/*.json",
        "examples/**/*.ipynb",
        "examples/**/*.txt",
        "examples/**/*.xlsx",
        "sites/ploemeur/**",
        "scripts/common/mcmc_diagnostics.py",
        "scripts/common/provenance.py",
        "scripts/common/reporting.py",
        "scripts/qualification/_archive_*.py",
        "scripts/qualification/build_multichain_archive.py",
        "scripts/qualification/build_ci_multichain_archive.py",
    ):
        assert f'- "{scientific_path}"' in workflow


def test_release_candidate_archives_the_tested_tag_and_distributions() -> None:
    workflow = (ci_archive.ROOT / ".github/workflows/release-candidate.yml").read_text(
        encoding="utf-8"
    )

    pytest_position = workflow.index("python -m pytest -q --run-extensive")
    download_position = workflow.index("actions/download-artifact", pytest_position)
    archive_position = workflow.index(
        "python -m scripts.qualification.build_ci_multichain_archive",
        download_position,
    )
    upload_position = workflow.index(
        "Preserve the qualification archive built from the release candidate",
        archive_position,
    )

    assert pytest_position < download_position < archive_position < upload_position
    assert "--mode publishable" in workflow
    assert '--expected-tag "$RELEASE_TAG"' in workflow
    assert "release-distributions-${{ inputs.tag }}" in workflow
    assert "multichain-qualification-${{ inputs.tag }}" in workflow
