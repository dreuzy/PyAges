# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for versioned public workflow result metadata."""

import errno
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

import pytest

from pyages import __version__
from pyages.workflows.runtime.manifest import (
    RESULT_SCHEMA_VERSION,
    ResultRun,
    begin_result_run,
    begin_staged_result_run,
    inspect_staged_result_run,
    inventory_staged_result_runs,
    promote_result_run,
    quarantine_staged_result_run,
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

    manifest_path = write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    sealed_state = json.loads(
        (run.working_directory / ".pyages-run-state.json").read_text(encoding="utf-8")
    )
    assert sealed_state["schema_version"] == 3
    assert (
        sealed_state["terminal_manifest_sha256"]
        == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
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


def test_result_run_is_an_opaque_non_constructible_handle(tmp_path) -> None:
    run = begin_staged_result_run(tmp_path / "results")

    with pytest.raises(TypeError):
        ResultRun()  # type: ignore[call-arg]

    assert not hasattr(run, "expected_publication_token")
    assert "publication_token" not in repr(run)


def test_promote_result_run_rejects_a_non_handle() -> None:
    with pytest.raises(TypeError, match="requires a ResultRun handle"):
        promote_result_run(object())  # type: ignore[arg-type]


def test_begin_staged_result_run_rejects_a_symbolic_link_target(tmp_path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "results"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory symlinks are unavailable: {error}")

    with pytest.raises(ValueError, match="symbolic link or junction"):
        begin_staged_result_run(link)

    assert actual.is_dir()


def test_begin_staged_result_run_rejects_a_mocked_junction(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "results"
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == target,
        raising=False,
    )

    with pytest.raises(ValueError, match="symbolic link or junction"):
        begin_staged_result_run(target)


def test_promotion_rejects_a_working_directory_replaced_by_a_symlink(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    actual_working = tmp_path / "actual-working"
    run.working_directory.replace(actual_working)
    try:
        run.working_directory.symlink_to(actual_working, target_is_directory=True)
    except OSError as error:
        actual_working.replace(run.working_directory)
        pytest.skip(f"Directory symlinks are unavailable: {error}")

    with pytest.raises(RuntimeError, match="Staged working path.*symbolic link"):
        promote_result_run(run)

    assert actual_working.is_dir()


def test_promotion_revalidates_a_public_target_junction(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == run.result_directory,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="Public result path.*junction"):
        promote_result_run(run)

    assert run.working_directory.is_dir()


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


def test_staged_run_rejects_a_terminal_manifest_changed_after_sealing(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    manifest_path = write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["configuration"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed after it was sealed"):
        promote_result_run(run)


def test_nested_control_filenames_remain_manifested_artifacts(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    nested = run.working_directory / "case"
    nested.mkdir()
    nested_manifest = nested / "result_manifest.json"
    nested_state = nested / ".pyages-run-state.json"
    nested_manifest.write_text("nested manifest\n", encoding="utf-8")
    nested_state.write_text("ordinary artifact\n", encoding="utf-8")

    manifest_path = write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    artifacts = json.loads(manifest_path.read_text(encoding="utf-8"))[
        "artifacts_sha256"
    ]

    assert artifacts == {
        "case/.pyages-run-state.json": hashlib.sha256(
            nested_state.read_bytes()
        ).hexdigest(),
        "case/result_manifest.json": hashlib.sha256(
            nested_manifest.read_bytes()
        ).hexdigest(),
    }
    promoted = promote_result_run(run)
    assert (promoted / "case" / ".pyages-run-state.json").is_file()


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


def test_promotion_rejects_an_active_child_in_the_incoming_tree(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    parent = begin_staged_result_run(tmp_path / "results")
    child = begin_staged_result_run(parent.working_directory / "nested")
    write_result_manifest(
        parent.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=parent.run_id,
    )

    with pytest.raises(RuntimeError, match="active nested staged run"):
        promote_result_run(parent)

    assert parent.working_directory.is_dir()
    assert child.working_directory.is_dir()
    assert not parent.result_directory.exists()


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


def test_promotion_restores_after_the_previous_tree_move_reports_failure(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    previous = result_directory / "previous.tsv"
    previous.write_text("previous\n", encoding="utf-8")
    run = begin_staged_result_run(result_directory)
    (run.working_directory / "samples.tsv").write_text("new\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    backup = tmp_path / f".pyages-prev-{run.run_id[:12]}"
    real_replace = Path.replace

    def fail_after_move(source, target):
        replaced = real_replace(source, target)
        if source == result_directory and target == backup:
            raise OSError("injected post-move failure")
        return replaced

    monkeypatch.setattr(Path, "replace", fail_after_move)

    with pytest.raises(OSError, match="injected post-move failure"):
        promote_result_run(run)

    assert previous.read_text(encoding="utf-8") == "previous\n"
    assert run.working_directory.is_dir()
    assert not backup.exists()


def test_promotion_reports_recovery_paths_when_restoration_fails(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    (result_directory / "previous.tsv").write_text("previous\n", encoding="utf-8")
    run = begin_staged_result_run(result_directory)
    (run.working_directory / "samples.tsv").write_text("new\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    backup = tmp_path / f".pyages-prev-{run.run_id[:12]}"
    real_replace = Path.replace

    def fail_commit_and_restore(source, target):
        if source == run.working_directory:
            raise OSError("injected commit failure")
        if source == backup:
            raise OSError("injected restoration failure")
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_commit_and_restore)

    with pytest.raises(RuntimeError, match="rollback could not restore") as caught:
        promote_result_run(run)

    message = str(caught.value)
    assert f"public={result_directory}" in message
    assert f"staging={run.working_directory}" in message
    assert f"backup={backup}" in message
    assert not result_directory.exists()
    assert run.working_directory.is_dir()
    assert backup.is_dir()


def test_windows_lock_retries_transient_contention(monkeypatch) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    class LockStream:
        @staticmethod
        def seek(_offset):
            return None

        @staticmethod
        def fileno():
            return 42

    class FakeMsvcrt:
        LK_NBLCK = 1
        attempts = 0

        @classmethod
        def locking(cls, _file_descriptor, mode, _length):
            assert mode == cls.LK_NBLCK
            cls.attempts += 1
            if cls.attempts < 3:
                raise OSError(errno.EACCES, "lock contention")

    sleeps = []
    monkeypatch.setattr(manifest_module, "msvcrt", FakeMsvcrt, raising=False)
    monkeypatch.setattr(manifest_module.time, "sleep", sleeps.append)

    manifest_module._acquire_windows_promotion_lock(LockStream())

    assert FakeMsvcrt.attempts == 3
    assert sleeps == [0.05, 0.05]


def test_promotion_lock_is_a_private_regular_file(tmp_path, monkeypatch) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    lock_directory = tmp_path / "private-locks"
    lock_directory.mkdir(mode=0o700)
    lock_path = lock_directory / "promotion.lock"
    monkeypatch.setattr(manifest_module, "_promotion_lock_path", lambda: lock_path)

    with manifest_module._promotion_lock(
        tmp_path / "results",
        "00000000-0000-0000-0000-000000000000",
    ):
        assert lock_path.is_file()
        assert not lock_path.is_symlink()

    metadata = os.lstat(lock_path)
    assert stat.S_ISREG(metadata.st_mode)
    assert metadata.st_nlink == 1
    if os.name != "nt":
        assert stat.S_IMODE(metadata.st_mode) & 0o077 == 0


def test_promotion_lock_refuses_a_junction_without_rewriting_it(
    tmp_path,
    monkeypatch,
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    lock_directory = tmp_path / "private-locks"
    lock_directory.mkdir(mode=0o700)
    lock_path = lock_directory / "promotion.lock"
    lock_path.write_bytes(b"do-not-rewrite")
    monkeypatch.setattr(manifest_module, "_promotion_lock_path", lambda: lock_path)
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == lock_path,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="symbolic link or junction"):
        with manifest_module._promotion_lock(
            tmp_path / "results",
            "00000000-0000-0000-0000-000000000000",
        ):
            pass

    assert lock_path.read_bytes() == b"do-not-rewrite"


def test_promotion_lock_refuses_a_symlink_without_rewriting_its_target(
    tmp_path,
    monkeypatch,
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    lock_directory = tmp_path / "private-locks"
    lock_directory.mkdir(mode=0o700)
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"preserve-me")
    lock_path = lock_directory / "promotion.lock"
    try:
        lock_path.symlink_to(victim)
    except OSError as error:
        pytest.skip(f"File symlinks are unavailable: {error}")
    monkeypatch.setattr(manifest_module, "_promotion_lock_path", lambda: lock_path)

    with pytest.raises(RuntimeError, match="symbolic link or junction"):
        with manifest_module._promotion_lock(
            tmp_path / "results",
            "00000000-0000-0000-0000-000000000000",
        ):
            pass

    assert victim.read_bytes() == b"preserve-me"


def test_staged_run_inspection_reports_unsealed_and_sealed_evidence(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")

    unsealed = inspect_staged_result_run(run.working_directory)

    assert unsealed.journal_status == "valid"
    assert unsealed.run_id == run.run_id
    assert unsealed.manifest_status == "absent"
    assert unsealed.artifacts_status == "not_checked"
    assert unsealed.publication_status == "current"
    assert not unsealed.promotable_now
    assert "not sealed" in unsealed.issues[0]

    artifact = run.working_directory / "samples.tsv"
    artifact.write_text("sample\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )

    sealed = inspect_staged_result_run(run.working_directory)

    assert sealed.manifest_status == "sealed"
    assert sealed.artifacts_status == "match"
    assert sealed.publication_status == "current"
    assert sealed.promotable_now
    assert sealed.issues == ()


def test_staged_run_inspection_diagnoses_artifact_and_cas_changes(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    run = begin_staged_result_run(result_directory)
    artifact = run.working_directory / "samples.tsv"
    artifact.write_text("original\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    artifact.write_text("changed\n", encoding="utf-8")
    result_directory.mkdir()
    (result_directory / "other.txt").write_text("concurrent\n", encoding="utf-8")

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.manifest_status == "sealed"
    assert inspection.artifacts_status == "mismatch"
    assert inspection.publication_status == "changed"
    assert not inspection.promotable_now
    assert any("artifacts differ" in issue for issue in inspection.issues)
    assert any("changed after staging" in issue for issue in inspection.issues)


def test_staged_run_inspection_diagnoses_a_changed_manifest_seal(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    manifest = write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    manifest.write_text("{}\n", encoding="utf-8")

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.manifest_status == "invalid"
    assert inspection.artifacts_status == "not_checked"
    assert not inspection.promotable_now
    assert any("changed after its journal seal" in issue for issue in inspection.issues)


def test_staged_run_inspection_diagnoses_a_structurally_invalid_journal(
    tmp_path,
) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    journal = run.working_directory / ".pyages-run-state.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    payload["baseline"] = []
    journal.write_text(json.dumps(payload), encoding="utf-8")

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.journal_status == "invalid"
    assert not inspection.promotable_now
    assert "baseline must be an object" in inspection.issues[0]


def test_staged_run_inspection_rejects_a_junction_run_journal(
    tmp_path,
    monkeypatch,
) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    journal = run.working_directory / ".pyages-run-state.json"
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == journal,
        raising=False,
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.journal_status == "invalid"
    assert not inspection.promotable_now
    assert "symbolic link or junction" in inspection.issues[0]


def test_staged_run_inspection_rejects_a_junction_terminal_manifest(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    manifest = write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == manifest,
        raising=False,
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.manifest_status == "invalid"
    assert inspection.artifacts_status == "not_checked"
    assert not inspection.promotable_now
    assert any("symbolic link or junction" in issue for issue in inspection.issues)


def test_staged_run_inspection_rejects_a_junction_artifact(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    artifact = run.working_directory / "samples.tsv"
    artifact.write_text("sample\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == artifact,
        raising=False,
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.manifest_status == "sealed"
    assert inspection.artifacts_status == "not_checked"
    assert not inspection.promotable_now
    assert any("symbolic link or junction" in issue for issue in inspection.issues)


def test_staged_run_inspection_rejects_an_artifact_symlink_outside_the_stage(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    artifact = run.working_directory / "samples.tsv"
    artifact.write_text("sample\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    external = tmp_path / "external.tsv"
    external.write_text("sample\n", encoding="utf-8")
    artifact.unlink()
    try:
        artifact.symlink_to(external)
    except OSError as error:
        pytest.skip(f"File symlinks are unavailable: {error}")

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.manifest_status == "sealed"
    assert inspection.artifacts_status == "not_checked"
    assert not inspection.promotable_now
    assert any("symbolic link or junction" in issue for issue in inspection.issues)


def test_staged_run_inspection_fails_closed_on_a_tree_walk_error(
    tmp_path,
    monkeypatch,
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    run = begin_staged_result_run(tmp_path / "results")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    real_walk = manifest_module.os.walk

    def fail_stage_walk(directory, *args, **kwargs):
        if Path(directory) == run.working_directory:
            kwargs["onerror"](PermissionError("injected unreadable subtree"))
        return real_walk(directory, *args, **kwargs)

    monkeypatch.setattr(manifest_module.os, "walk", fail_stage_walk)

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.artifacts_status == "not_checked"
    assert not inspection.promotable_now
    assert any("unreadable subtree" in issue for issue in inspection.issues)


def test_staged_run_inspection_and_quarantine_reject_a_public_junction(
    tmp_path,
    monkeypatch,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    run = begin_staged_result_run(result_directory)
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == result_directory,
        raising=False,
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.publication_status == "not_checked"
    assert not inspection.promotable_now
    assert any("public result path" in issue.lower() for issue in inspection.issues)
    with pytest.raises(RuntimeError, match="Public result path.*junction"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)
    assert run.working_directory.is_dir()


def test_staged_run_journal_preserves_and_rejects_a_public_symlink_path(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    run = begin_staged_result_run(result_directory)
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )
    result_directory.rmdir()
    try:
        result_directory.symlink_to(redirected, target_is_directory=True)
    except OSError as error:
        result_directory.mkdir()
        pytest.skip(f"Directory symlinks are unavailable: {error}")

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.result_directory == result_directory
    assert inspection.publication_status == "not_checked"
    assert not inspection.promotable_now
    assert any("symbolic link or junction" in issue for issue in inspection.issues)
    with pytest.raises(RuntimeError, match="Public result path.*junction"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)
    assert run.working_directory.is_dir()


def test_staged_run_inspection_and_quarantine_reject_a_public_file(
    tmp_path,
) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    result_directory = tmp_path / "results"
    result_directory.mkdir()
    run = begin_staged_result_run(result_directory)
    result_directory.rmdir()
    result_directory.write_text("not a result directory\n", encoding="utf-8")
    write_result_manifest(
        run.working_directory,
        workflow="single_date",
        config_path=config,
        run_id=run.run_id,
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.publication_status == "not_checked"
    assert not inspection.promotable_now
    assert any("not a real directory" in issue for issue in inspection.issues)
    with pytest.raises(RuntimeError, match="not a real directory"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)
    assert run.working_directory.is_dir()


def test_inspection_diagnoses_a_broken_junction_before_missing_path(
    tmp_path,
    monkeypatch,
) -> None:
    candidate = tmp_path / ".pyages-deadbeef-000"
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == candidate,
        raising=False,
    )

    inspection = inspect_staged_result_run(candidate)

    assert inspection.journal_status == "invalid"
    assert "symbolic link or junction" in inspection.issues[0]


def test_staged_run_inspection_does_not_scan_an_unsafe_journal_target(
    tmp_path,
    monkeypatch,
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    run = begin_staged_result_run(tmp_path / "results")
    journal = run.working_directory / ".pyages-run-state.json"
    payload = json.loads(journal.read_text(encoding="utf-8"))
    payload["result_directory"] = str(tmp_path.anchor)
    journal.write_text(json.dumps(payload), encoding="utf-8")

    def fail_if_scanned(_directory):
        raise AssertionError("unsafe public target must not be scanned")

    monkeypatch.setattr(manifest_module, "_publication_token", fail_if_scanned)
    monkeypatch.setattr(
        manifest_module, "_assert_no_nested_staged_runs", fail_if_scanned
    )

    inspection = inspect_staged_result_run(run.working_directory)

    assert inspection.journal_status == "valid"
    assert inspection.publication_status == "not_checked"
    assert not inspection.promotable_now
    assert any("filesystem root" in issue for issue in inspection.issues)


def test_staged_run_inventory_keeps_invalid_and_missing_journals_visible(
    tmp_path,
) -> None:
    valid = begin_staged_result_run(tmp_path / "nested" / "results")
    malformed = tmp_path / ".pyages-deadbeef-000"
    malformed.mkdir()
    (malformed / ".pyages-run-state.json").write_text("{", encoding="utf-8")
    missing = tmp_path / ".pyages-cafebabe-fee"
    missing.mkdir()
    quarantined = tmp_path / ".pyages-quarantine-000000000000"
    quarantined.mkdir()
    (quarantined / ".pyages-01234567-89a").mkdir()

    inspections = inventory_staged_result_runs(tmp_path)

    assert [item.stage_directory for item in inspections] == sorted(
        [malformed, missing, valid.working_directory],
        key=lambda path: str(path).casefold(),
    )
    by_path = {item.stage_directory: item for item in inspections}
    assert by_path[malformed].journal_status == "invalid"
    assert by_path[missing].journal_status == "missing"
    assert by_path[valid.working_directory].journal_status == "valid"


def test_staged_run_inventory_reports_but_does_not_follow_a_stage_link(
    tmp_path,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / ".pyages-deadbeef-000"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory symlinks are unavailable: {error}")

    inspections = inventory_staged_result_runs(tmp_path)

    assert len(inspections) == 1
    assert inspections[0].stage_directory == link
    assert inspections[0].journal_status == "invalid"
    assert "symbolic link or junction" in inspections[0].issues[0]


def test_staged_run_inventory_reports_a_stage_shaped_file(tmp_path) -> None:
    candidate = tmp_path / ".pyages-deadbeef-000"
    candidate.write_text("not a directory\n", encoding="utf-8")

    inspections = inventory_staged_result_runs(tmp_path)

    assert len(inspections) == 1
    assert inspections[0].stage_directory == candidate
    assert inspections[0].journal_status == "invalid"
    assert "not a directory" in inspections[0].issues[0]


def test_begin_staged_run_rejects_a_junction_inside_the_public_tree(
    tmp_path,
    monkeypatch,
) -> None:
    result_directory = tmp_path / "results"
    nested = result_directory / "redirected"
    nested.mkdir(parents=True)
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == nested,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="contains a symbolic link or junction"):
        begin_staged_result_run(result_directory)

    assert not any(tmp_path.glob(".pyages-????????-???"))


def test_quarantine_requires_exact_run_id_and_preserves_the_complete_tree(
    tmp_path,
) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    artifact = run.working_directory / "partial.tsv"
    artifact.write_text("partial\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Run identity mismatch"):
        quarantine_staged_result_run(
            run.working_directory,
            run_id="00000000-0000-0000-0000-000000000000",
        )

    quarantine = quarantine_staged_result_run(
        run.working_directory,
        run_id=run.run_id,
    )

    assert quarantine == tmp_path / f".pyages-quarantine-{run.run_id[:12]}"
    assert not run.working_directory.exists()
    assert (quarantine / "partial.tsv").read_text(encoding="utf-8") == "partial\n"
    assert (quarantine / ".pyages-run-state.json").is_file()
    assert inventory_staged_result_runs(tmp_path) == ()


def test_quarantine_refuses_a_junction_stage_path(tmp_path, monkeypatch) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    monkeypatch.setattr(
        Path,
        "is_junction",
        lambda path: path == run.working_directory,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="Staging path.*junction"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)

    assert run.working_directory.is_dir()


def test_quarantine_refuses_an_existing_destination(tmp_path) -> None:
    run = begin_staged_result_run(tmp_path / "results")
    quarantine = tmp_path / f".pyages-quarantine-{run.run_id[:12]}"
    quarantine.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)

    assert run.working_directory.is_dir()


def test_quarantine_revalidates_the_target_after_acquiring_the_lock(
    tmp_path,
    monkeypatch,
) -> None:
    from pyages.workflows.runtime import manifest as manifest_module

    run = begin_staged_result_run(tmp_path / "results")
    journal = run.working_directory / ".pyages-run-state.json"

    @contextmanager
    def mutate_target_while_locking(_result_directory, _run_id):
        payload = json.loads(journal.read_text(encoding="utf-8"))
        payload["result_directory"] = str(tmp_path / "different-results")
        journal.write_text(json.dumps(payload), encoding="utf-8")
        yield

    monkeypatch.setattr(
        manifest_module,
        "_promotion_lock",
        mutate_target_while_locking,
    )

    with pytest.raises(RuntimeError, match="target changed"):
        quarantine_staged_result_run(run.working_directory, run_id=run.run_id)

    assert run.working_directory.is_dir()


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
