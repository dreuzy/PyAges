# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for versioned public workflow result metadata."""

import hashlib
import json
from pathlib import Path

from pyages import __version__
from pyages.workflows.runtime.manifest import (
    RESULT_SCHEMA_VERSION,
    begin_result_run,
    write_result_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_result_manifest_is_versioned_and_deterministic(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    artifact = tmp_path / "samples.csv"
    artifact.write_text("mu\n10\n", encoding="utf-8")
    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[config],
        details={"lpm": "exp"},
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RESULT_SCHEMA_VERSION == 2
    assert payload["status"] == "complete"
    assert payload["workflow"] == "single_date"
    assert payload["pyages_version"] == __version__
    assert payload["details"] == {"lpm": "exp"}
    assert (
        payload["configuration"]["sha256"]
        == hashlib.sha256(config.read_bytes()).hexdigest()
    )
    assert payload["inputs"][0]["sha256"] == payload["configuration"]["sha256"]
    assert payload["artifacts_sha256"] == {
        "case.yaml": hashlib.sha256(config.read_bytes()).hexdigest(),
        "samples.csv": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    assert payload["environment"]["dependencies"]["numpy"]
    assert set(payload["environment"]) == {
        "dependencies",
        "implementation",
        "platform",
        "python",
    }
    assert "tracked_workspace_sha256" in payload["repository"]


def test_result_manifest_top_level_fields_are_documented(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        details={"lpm": "exp"},
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    documentation = (ROOT / "docs" / "reference" / "results.md").read_text(
        encoding="utf-8"
    )

    for field in payload:
        assert f"`{field}`" in documentation


def test_begin_result_run_invalidates_only_the_previous_success_marker(
    tmp_path,
) -> None:
    artifact = tmp_path / "samples.csv"
    artifact.write_text("mu\n10\n", encoding="utf-8")
    manifest = tmp_path / "result_manifest.json"
    manifest.write_text('{"status": "complete"}\n', encoding="utf-8")

    assert begin_result_run(tmp_path) == tmp_path.resolve()

    assert artifact.is_file()
    assert not manifest.exists()


def test_result_manifest_expands_and_deduplicates_input_directories(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    resources = tmp_path / "resources"
    resources.mkdir()
    first = resources / "a.txt"
    second = resources / "b.txt"
    first.write_text("a\n", encoding="utf-8")
    second.write_text("b\n", encoding="utf-8")

    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[resources, first],
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [item["path"] for item in payload["inputs"]] == [
        "external/0/a.txt",
        "external/0/b.txt",
    ]


def test_result_manifest_distinguishes_external_roots_with_same_filename(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / "recharge.csv").write_text("first\n", encoding="utf-8")
    (second_root / "recharge.csv").write_text("second\n", encoding="utf-8")

    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[first_root, second_root],
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [item["path"] for item in payload["inputs"]] == [
        "external/0/recharge.csv",
        "external/1/recharge.csv",
    ]


def test_result_manifest_keeps_repository_root_files_repository_relative(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")

    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[ROOT / "pyproject.toml"],
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["inputs"][0]["path"] == "pyproject.toml"


def test_result_manifest_tolerates_an_unavailable_git_executable(
    tmp_path, monkeypatch
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")

    def missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git executable not found")

    monkeypatch.setattr(
        "pyages.workflows.runtime.manifest.subprocess.run",
        missing_git,
    )
    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
    )

    repository = json.loads(target.read_text(encoding="utf-8"))["repository"]
    assert repository["git_head"] is None
    assert repository["dirty"] is None
    assert repository["tracked_diff_sha256"] is None
