# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for versioned public workflow result metadata."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from pyages import __version__
from pyages.workflows.runtime.manifest import (
    RESULT_SCHEMA_VERSION,
    begin_result_run,
    begin_staged_result_run,
    promote_result_run,
    write_failure_manifest,
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


def test_failure_manifest_preserves_rejected_run_provenance(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    source = tmp_path / "observations.tsv"
    source.write_text("element\tconcentration\ncfc11\t1\n", encoding="utf-8")
    artifact = tmp_path / "chains" / "chain_001" / "samples.tsv"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("mu\n10\n", encoding="utf-8")
    error = RuntimeError("R-hat exceeded its configured threshold")

    target = write_failure_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[source],
        details={"lpm": "exp"},
        error=error,
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RESULT_SCHEMA_VERSION
    assert payload["status"] == "failed"
    assert payload["failure"] == {
        "type": "RuntimeError",
        "message": "R-hat exceeded its configured threshold",
    }
    assert (
        payload["configuration"]["sha256"]
        == hashlib.sha256(config.read_bytes()).hexdigest()
    )
    assert (
        payload["inputs"][0]["sha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )
    assert "chains/chain_001/samples.tsv" in payload["artifacts_sha256"]
    documentation = (ROOT / "docs" / "reference" / "results.md").read_text(
        encoding="utf-8"
    )
    assert "`failure`" in documentation
    assert "`failed`" in documentation


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
    state = json.loads(
        (tmp_path / ".pyages-run-state.json").read_text(encoding="utf-8")
    )
    assert state["status"] == "started"
    assert state["mode"] == "in_place"


def test_staged_run_promotes_only_the_current_run_artifacts(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    stale = result_directory / "stale-samples.tsv"
    stale.write_text("old\n", encoding="utf-8")
    (result_directory / "result_manifest.json").write_text(
        '{"status": "complete"}\n', encoding="utf-8"
    )

    run = begin_staged_result_run(result_directory)
    current = run.working_directory / "chains" / "samples.tsv"
    current.parent.mkdir()
    current.write_text("new\n", encoding="utf-8")
    state = json.loads(
        (run.working_directory / ".pyages-run-state.json").read_text(encoding="utf-8")
    )
    assert state["status"] == "started"
    assert state["run_id"] == run.run_id
    assert stale.is_file()
    assert (result_directory / "result_manifest.json").is_file()

    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    promoted = promote_result_run(run)

    assert promoted == result_directory.resolve()
    assert (promoted / "chains" / "samples.tsv").read_text(encoding="utf-8") == (
        "new\n"
    )
    assert not (promoted / "stale-samples.tsv").exists()
    assert not (promoted / ".pyages-run-state.json").exists()
    payload = json.loads(
        (promoted / "result_manifest.json").read_text(encoding="utf-8")
    )
    assert payload["run_id"] == run.run_id
    assert payload["started_at_utc"] == run.started_at_utc
    assert payload["artifacts_sha256"] == {
        "chains/samples.tsv": hashlib.sha256(
            (promoted / "chains" / "samples.tsv").read_bytes()
        ).hexdigest()
    }


def test_staged_run_rejects_artifacts_changed_after_terminal_manifest(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    artifact = run.working_directory / "samples.tsv"
    artifact.write_text("first\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )

    artifact.write_text("changed\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed after terminal manifest"):
        promote_result_run(run)
    assert run.working_directory.is_dir()
    assert not run.result_directory.exists()


def test_staged_run_uses_compare_and_swap_for_concurrent_promotions(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    first = begin_staged_result_run(result_directory)
    second = begin_staged_result_run(result_directory)
    for run, value in ((first, "first\n"), (second, "second\n")):
        (run.working_directory / "samples.tsv").write_text(value, encoding="utf-8")
        write_result_manifest(
            run.working_directory,
            workflow="single_date",
            config_path=config,
            run_id=run.run_id,
        )

    promote_result_run(second)

    with pytest.raises(RuntimeError, match="changed after this run started"):
        promote_result_run(first)
    assert (result_directory / "samples.tsv").read_text(encoding="utf-8") == (
        "second\n"
    )


def test_ancestor_promotion_preserves_an_active_nested_staging_tree(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    previous_manifest = result_directory / "result_manifest.json"
    previous_manifest.write_text('{"status": "complete"}\n', encoding="utf-8")

    nested = begin_staged_result_run(result_directory / "nested")
    ancestor = begin_staged_result_run(result_directory)
    (ancestor.working_directory / "samples.tsv").write_text(
        "ancestor\n", encoding="utf-8"
    )
    write_result_manifest(
        ancestor.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=ancestor.run_id,
    )

    with pytest.raises(RuntimeError, match="active nested staged run"):
        promote_result_run(ancestor)

    assert nested.working_directory.is_dir()
    assert previous_manifest.is_file()
    assert ancestor.working_directory.is_dir()


def test_nested_publication_invalidates_an_older_ancestor_run(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    (result_directory / "result_manifest.json").write_text(
        '{"status": "complete"}\n', encoding="utf-8"
    )
    ancestor = begin_staged_result_run(result_directory)
    nested = begin_staged_result_run(result_directory / "nested")
    (nested.working_directory / "samples.tsv").write_text("nested\n", encoding="utf-8")
    write_result_manifest(
        nested.working_directory,
        workflow="temporal",
        config_path=config,
        run_id=nested.run_id,
    )
    promote_result_run(nested)
    (ancestor.working_directory / "samples.tsv").write_text(
        "ancestor\n", encoding="utf-8"
    )
    write_result_manifest(
        ancestor.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=ancestor.run_id,
    )

    with pytest.raises(RuntimeError, match="changed after this run started"):
        promote_result_run(ancestor)

    assert (result_directory / "nested" / "samples.tsv").read_text(
        encoding="utf-8"
    ) == "nested\n"


def test_promotion_restores_the_previous_tree_when_the_commit_rename_fails(
    tmp_path, monkeypatch
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    previous = result_directory / "previous.tsv"
    previous.write_text("previous\n", encoding="utf-8")
    previous_manifest = result_directory / "result_manifest.json"
    previous_manifest.write_text('{"status": "complete"}\n', encoding="utf-8")
    run = begin_staged_result_run(result_directory)
    (run.working_directory / "samples.tsv").write_text("new\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    real_replace = Path.replace

    def fail_commit(source, target):
        if source == run.working_directory:
            raise OSError("injected commit rename failure")
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_commit)

    with pytest.raises(OSError, match="injected commit rename failure"):
        promote_result_run(run)

    assert previous.read_text(encoding="utf-8") == "previous\n"
    assert previous_manifest.is_file()
    assert run.working_directory.is_dir()
    assert not list(tmp_path.glob(".pyages-prev-*"))


def test_staged_run_rejects_a_mismatched_run_identity(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")

    try:
        write_result_manifest(
            run.working_directory,
            workflow="single_date",
            config_path=config,
            run_id="00000000-0000-0000-0000-000000000000",
        )
    except RuntimeError as error:
        assert "Run identity mismatch" in str(error)
    else:
        raise AssertionError("A mismatched run identity must not be finalized")

    assert not (run.working_directory / "result_manifest.json").exists()


def test_in_place_run_inventory_excludes_unchanged_older_artifacts(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    stale = result_directory / "stale.tsv"
    stale.write_text("old\n", encoding="utf-8")

    begin_result_run(result_directory)
    current = result_directory / "current.tsv"
    current.write_text("new\n", encoding="utf-8")
    target = write_result_manifest(
        result_directory,
        workflow="single_date",
        config_path=config,
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["artifacts_sha256"] == {
        "current.tsv": hashlib.sha256(current.read_bytes()).hexdigest()
    }
    assert stale.is_file()
    assert not (result_directory / ".pyages-run-state.json").exists()


def test_in_place_inventory_detects_same_size_preserved_mtime_rewrites(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    artifact = result_directory / "samples.tsv"
    artifact.write_text("old", encoding="utf-8")
    original = artifact.stat()

    begin_result_run(result_directory)
    artifact.write_text("new", encoding="utf-8")
    os.utime(artifact, ns=(original.st_atime_ns, original.st_mtime_ns))
    target = write_result_manifest(
        result_directory,
        workflow="single_date",
        config_path=config,
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["artifacts_sha256"] == {
        "samples.tsv": hashlib.sha256(b"new").hexdigest()
    }


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


def test_untracked_installed_source_is_not_attributed_to_an_enclosing_worktree(
    tmp_path, monkeypatch
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    enclosing_repository = tmp_path / "checkout"
    installed_source = (
        enclosing_repository
        / ".venv"
        / "Lib"
        / "site-packages"
        / "pyages"
        / "workflows"
        / "runtime"
        / "manifest.py"
    )

    def git_result(_repository, *args, **_kwargs):
        if args == ("rev-parse", "--show-toplevel"):
            return str(enclosing_repository)
        if args[:2] == ("ls-files", "--error-unmatch"):
            return None
        raise AssertionError(f"Unexpected Git command: {args}")

    monkeypatch.setattr(manifest_module, "_run_git", git_result)

    assert manifest_module._source_repository(installed_source) is None


def test_manifest_records_distribution_provenance_without_a_source_worktree(
    tmp_path, monkeypatch
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    monkeypatch.setattr(manifest_module, "_source_repository", lambda _path: None)

    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert payload["package"]["name"].lower() == "pyages"
    assert payload["package"]["version"]
    assert payload["package"]["version_matches_runtime"] == (
        payload["package"]["version"] == __version__
    )
    assert payload["package"]["source"] == "installed_distribution"
    assert payload["package"]["metadata_sha256"]
    assert payload["repository"] == {
        "git_head": None,
        "dirty": None,
        "status_porcelain_v2": [],
        "tracked_diff_sha256": None,
        "tracked_workspace_sha256": None,
        "tracked_file_count": 0,
    }


def test_distribution_provenance_hashes_pep610_and_record_metadata(monkeypatch) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    direct_url = '{"url": "file:///wheelhouse/pyages.whl"}'
    record = "pyages/__init__.py,sha256=abc,12\npyages-1.dist-info/RECORD,,\n"

    class Distribution:
        version = "1.2.3"
        metadata = {"Name": "pyages"}
        files = ("pyages/__init__.py", "pyages-1.dist-info/RECORD")

        @staticmethod
        def read_text(filename):
            return {
                "direct_url.json": direct_url,
                "RECORD": record,
                "METADATA": "Name: pyages\nVersion: 1.2.3\n",
            }.get(filename)

    monkeypatch.setattr(
        manifest_module.importlib.metadata,
        "distribution",
        lambda _name: Distribution(),
    )

    provenance = manifest_module._distribution_provenance(from_worktree=False)

    assert provenance["direct_url"] == {"url": "file:///wheelhouse/pyages.whl"}
    assert (
        provenance["record_sha256"]
        == hashlib.sha256(record.encode("utf-8")).hexdigest()
    )
    assert provenance["record_file_count"] == 2
    assert provenance["installed_file_count"] == 2
