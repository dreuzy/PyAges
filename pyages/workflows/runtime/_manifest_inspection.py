# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file validates journals and inspects interrupted workflow stages.

"""Provide read-only inspection of managed workflow staging directories."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from pyages.workflows.runtime._manifest_artifacts import (
    _RUN_STATE_FILENAME,
    _TERMINAL_MANIFEST_FILENAME,
    _publication_token,
    _snapshot,
)
from pyages.workflows.runtime._manifest_fs import (
    absolute_without_resolving as _absolute_without_resolving,
)
from pyages.workflows.runtime._manifest_fs import (
    is_link_or_junction as _is_link_or_junction,
)
from pyages.workflows.runtime._manifest_fs import (
    path_entry_exists as _path_entry_exists,
)
from pyages.workflows.runtime._manifest_fs import (
    raise_walk_error as _raise_walk_error,
)
from pyages.workflows.runtime._manifest_fs import (
    read_strict_regular_file as _read_strict_regular_file,
)
from pyages.workflows.runtime._manifest_fs import (
    strict_tree_entries as _strict_tree_entries,
)
from pyages.workflows.runtime._manifest_types import (
    RunState as _RunState,
)
from pyages.workflows.runtime._manifest_types import StagedRunInspection

_RUN_STATE_SCHEMA_VERSION = 4

_RUN_STATE_FIELDS = {
    "schema_version",
    "status",
    "run_id",
    "started_at_utc",
    "mode",
    "result_directory",
    "expected_publication_token",
    "terminal_manifest_sha256",
}


def _is_sha256_digest(value: object) -> bool:
    """Return whether ``value`` is one canonical lowercase SHA-256 digest."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validated_publication_token(value: object) -> str:
    """Validate the compare-and-swap token in a staged-run journal."""
    if not isinstance(value, str) or not (
        value == "absent"
        or (
            value.startswith("tree:") and _is_sha256_digest(value.removeprefix("tree:"))
        )
    ):
        raise ValueError("staged state has an invalid publication token")
    return value


def _validated_run_id(value: object) -> str:
    """Validate the canonical complete UUID stored in a run journal."""
    if not isinstance(value, str):
        raise ValueError("run_id must be a string")
    canonical = str(uuid.UUID(value))
    if value != canonical:
        raise ValueError("run_id must use canonical complete UUID syntax")
    return canonical


def _validated_started_at_utc(value: object) -> str:
    """Validate the timezone-aware start timestamp stored in a run journal."""
    if not isinstance(value, str):
        raise ValueError("started_at_utc must be a string")
    started_at = datetime.fromisoformat(value)
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("started_at_utc must include a timezone")
    return value


def _validated_result_directory(value: object) -> Path:
    """Validate and preserve an absolute public path without resolving links."""
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("result_directory must be an absolute path")
    return _absolute_without_resolving(value)


def _validated_terminal_manifest_digest(value: object) -> str | None:
    """Validate an optional terminal-manifest seal from a run journal."""
    if value is not None and not _is_sha256_digest(value):
        raise ValueError("invalid terminal manifest digest")
    return value


def _parsed_run_state(payload: object) -> _RunState:
    """Build a run state from a fully validated JSON-compatible payload."""
    if not isinstance(payload, dict):
        raise ValueError("state payload must be an object")
    if set(payload) != _RUN_STATE_FIELDS:
        raise ValueError("state payload fields do not match the current schema")
    mode = payload["mode"]
    if payload["status"] != "started" or mode != "staged":
        raise ValueError("unsupported state")
    if payload.get("schema_version") != _RUN_STATE_SCHEMA_VERSION:
        raise ValueError("unsupported state schema")
    return _RunState(
        run_id=_validated_run_id(payload["run_id"]),
        started_at_utc=_validated_started_at_utc(payload["started_at_utc"]),
        mode="staged",
        result_directory=_validated_result_directory(payload["result_directory"]),
        expected_publication_token=_validated_publication_token(
            payload.get("expected_publication_token")
        ),
        terminal_manifest_sha256=_validated_terminal_manifest_digest(
            payload.get("terminal_manifest_sha256")
        ),
        managed=True,
    )


def _read_run_state(directory: Path) -> _RunState | None:
    state_path = directory / _RUN_STATE_FILENAME
    if not _path_entry_exists(state_path):
        return None
    try:
        payload: object = json.loads(
            _read_strict_regular_file(
                state_path,
                label="Managed run journal",
            ).decode("utf-8")
        )
        return _parsed_run_state(payload)
    except (
        AttributeError,
        KeyError,
        RuntimeError,
        TypeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            f"Invalid PyAges run state: {state_path}: {error}"
        ) from error


def _is_staging_directory_name(name: str) -> bool:
    """Return whether a name has the managed staging-directory shape."""
    prefix = ".pyages-"
    if not name.startswith(prefix):
        return False
    suffix = name[len(prefix) :]
    return (
        len(suffix) == 12
        and suffix[8] == "-"
        and all(
            character in "0123456789abcdef" for character in suffix[:8] + suffix[9:]
        )
    )


def _invalid_stage_inspection(
    stage_directory: Path,
    *,
    journal_status: Literal["missing", "invalid"],
    issue: str,
) -> StagedRunInspection:
    """Build a diagnosis for a candidate whose journal cannot be trusted."""
    return StagedRunInspection(
        stage_directory=stage_directory,
        journal_status=journal_status,
        run_id=None,
        started_at_utc=None,
        result_directory=None,
        manifest_status="not_checked",
        artifacts_status="not_checked",
        publication_status="not_checked",
        promotable_now=False,
        issues=(issue,),
    )


def _stage_structure_issues(stage: Path, state: _RunState) -> list[str]:
    """Return journal/path inconsistencies that make a stage unsafe."""
    issues: list[str] = []
    if state.mode != "staged":
        issues.append(f"Journal mode is {state.mode!r}, not 'staged'.")
    expected_name = f".pyages-{state.run_id[:12]}"
    if stage.name != expected_name or stage.parent != state.result_directory.parent:
        issues.append(
            "Staging and public result paths do not form the managed sibling pair."
        )
    if state.result_directory == state.result_directory.parent:
        issues.append("The journal targets a filesystem root.")
    if _is_link_or_junction(state.result_directory):
        issues.append("The public result path is a symbolic link or junction.")
    elif (
        _path_entry_exists(state.result_directory)
        and not state.result_directory.is_dir()
    ):
        issues.append("The public result path is not a real directory.")
    return issues


def _inspect_terminal_evidence(
    stage: Path,
    state: _RunState,
    issues: list[str],
) -> tuple[
    Literal["not_checked", "absent", "unsealed", "sealed", "invalid"],
    Literal["not_checked", "match", "mismatch"],
]:
    """Diagnose a terminal seal and the artifacts it commits to.

    Validation is intentionally ordered: first compare the manifest bytes with
    the digest sealed in the journal, then parse and match the run identity,
    and only then rehash the artifact tree.  Later evidence is never trusted
    when an earlier link in that chain is absent or inconsistent.
    """
    manifest_path = stage / _TERMINAL_MANIFEST_FILENAME
    if not _path_entry_exists(manifest_path):
        if state.terminal_manifest_sha256 is None:
            issues.append("The terminal manifest is absent and the run is not sealed.")
            return "absent", "not_checked"
        issues.append("The sealed terminal manifest is missing.")
        return "invalid", "not_checked"
    if state.terminal_manifest_sha256 is None:
        issues.append("A terminal manifest exists but its journal seal is absent.")
        return "unsealed", "not_checked"
    try:
        manifest_bytes = _read_strict_regular_file(
            manifest_path,
            label="Sealed terminal manifest",
        )
        manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    except (OSError, RuntimeError) as error:
        issues.append(f"The sealed terminal manifest is unreadable: {error}")
        return "invalid", "not_checked"
    if manifest_digest != state.terminal_manifest_sha256:
        issues.append("The terminal manifest changed after its journal seal.")
        return "invalid", "not_checked"
    try:
        terminal_payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        issues.append(f"The sealed terminal manifest is unreadable: {error}")
        return "invalid", "not_checked"
    if not isinstance(terminal_payload, dict) or (
        terminal_payload.get("run_id") != state.run_id
        or terminal_payload.get("status") not in {"complete", "failed"}
    ):
        issues.append("The terminal manifest does not match the journal run.")
        return "invalid", "not_checked"
    try:
        actual_artifacts = _snapshot(stage)
    except (OSError, RuntimeError) as error:
        issues.append(f"Staged artifacts could not be inventoried: {error}")
        return "sealed", "not_checked"
    if terminal_payload.get("artifacts_sha256") == actual_artifacts:
        return "sealed", "match"
    issues.append("Staged artifacts differ from the terminal manifest.")
    return "sealed", "mismatch"


def _inspect_publication_state(
    state: _RunState, issues: list[str]
) -> Literal["not_checked", "current", "changed"]:
    """Diagnose the point-in-time compare-and-swap publication token."""
    if state.expected_publication_token is None:
        return "not_checked"
    public = state.result_directory
    if _is_link_or_junction(public):
        issues.append("The public result path is a symbolic link or junction.")
        return "not_checked"
    if _path_entry_exists(public) and not public.is_dir():
        issues.append("The public result path is not a real directory.")
        return "not_checked"
    try:
        current_token = _publication_token(public)
    except (OSError, RuntimeError) as error:
        issues.append(f"The public result tree could not be inventoried: {error}")
        return "not_checked"
    if current_token == state.expected_publication_token:
        return "current"
    issues.append("The public result tree changed after staging began.")
    return "changed"


def _append_nested_stage_issues(
    stage: Path,
    state: _RunState,
    issues: list[str],
) -> None:
    """Add promotion-blocking nested-stage diagnostics."""
    try:
        _assert_no_nested_staged_runs(state.result_directory)
        _assert_no_nested_staged_runs(stage)
    except (OSError, RuntimeError) as error:
        issues.append(str(error))


def _inspection_from_valid_state(
    stage: Path,
    state: _RunState,
) -> StagedRunInspection:
    """Assemble all read-only diagnostics for one parsed journal."""
    structure_issues = _stage_structure_issues(stage, state)
    issues = list(structure_issues)
    manifest_status, artifacts_status = _inspect_terminal_evidence(
        stage,
        state,
        issues,
    )
    publication_status: Literal["not_checked", "current", "changed"] = "not_checked"
    if not structure_issues:
        publication_status = _inspect_publication_state(state, issues)
        _append_nested_stage_issues(stage, state, issues)
    promotable_now = (
        not issues
        and manifest_status == "sealed"
        and artifacts_status == "match"
        and publication_status == "current"
    )
    return StagedRunInspection(
        stage_directory=stage,
        journal_status="valid",
        run_id=state.run_id,
        started_at_utc=state.started_at_utc,
        result_directory=state.result_directory,
        manifest_status=manifest_status,
        artifacts_status=artifacts_status,
        publication_status=publication_status,
        promotable_now=promotable_now,
        issues=tuple(issues),
    )


def inspect_staged_result_run(stage_directory: str | Path) -> StagedRunInspection:
    """Inspect one staging candidate without changing filesystem state.

    The journal, terminal-manifest seal, artifact inventory, publication CAS
    token, and nested-stage constraints are checked. Malformed or incomplete
    evidence is returned as a diagnosis rather than raised, so an operator can
    inventory interrupted work. Filesystem lookup failures still raise their
    normal exceptions.

    Parameters
    ----------
    stage_directory : str or pathlib.Path
        Existing directory to inspect. A final symbolic link or junction is
        diagnosed as invalid and is never followed.

    Returns
    -------
    StagedRunInspection
        Immutable point-in-time diagnosis. No lock is acquired and no file is
        created, changed, renamed, or removed.

    Raises
    ------
    FileNotFoundError
        If ``stage_directory`` does not exist.
    NotADirectoryError
        If ``stage_directory`` is not a directory.
    """
    requested = _absolute_without_resolving(stage_directory)
    if _is_link_or_junction(requested):
        return _invalid_stage_inspection(
            requested,
            journal_status="invalid",
            issue="The staging candidate is a symbolic link or junction.",
        )
    if not _path_entry_exists(requested):
        raise FileNotFoundError(f"Staging candidate does not exist: {requested}")
    if not requested.is_dir():
        raise NotADirectoryError(f"Staging candidate is not a directory: {requested}")
    stage = requested.resolve()
    state_path = stage / _RUN_STATE_FILENAME
    if not _path_entry_exists(state_path):
        return _invalid_stage_inspection(
            stage,
            journal_status="missing",
            issue=f"Managed run journal is missing: {state_path}",
        )
    try:
        state = _read_run_state(stage)
    except (RuntimeError, UnicodeError) as error:
        return _invalid_stage_inspection(
            stage,
            journal_status="invalid",
            issue=str(error),
        )
    if state is None:  # pragma: no cover - guarded by the journal existence check
        return _invalid_stage_inspection(
            stage,
            journal_status="missing",
            issue=f"Managed run journal is missing: {state_path}",
        )
    return _inspection_from_valid_state(stage, state)


def _discover_staging_candidates(search_root: Path) -> list[Path]:
    """Find candidate names without traversing managed or redirected trees."""
    candidates: list[Path] = []
    for current, directory_names, filenames in os.walk(
        search_root,
        onerror=_raise_walk_error,
        followlinks=False,
    ):
        current_path = Path(current)
        for name in list(directory_names):
            candidate = current_path / name
            if _is_staging_directory_name(name):
                candidates.append(candidate)
                directory_names.remove(name)
            elif _is_link_or_junction(candidate) or name.startswith(
                (".pyages-prev-", ".pyages-quarantine-")
            ):
                directory_names.remove(name)
        candidates.extend(
            current_path / name
            for name in filenames
            if _is_staging_directory_name(name)
        )
    return sorted(candidates, key=lambda path: str(path).casefold())


def _inspect_discovered_candidate(candidate: Path) -> StagedRunInspection:
    """Inspect a discovered candidate while tolerating a concurrent removal."""
    try:
        return inspect_staged_result_run(candidate)
    except (FileNotFoundError, NotADirectoryError) as error:
        return _invalid_stage_inspection(
            candidate,
            journal_status="invalid",
            issue=f"Staging candidate changed during inventory: {error}",
        )


def inventory_staged_result_runs(root: str | Path) -> tuple[StagedRunInspection, ...]:
    """Recursively inventory managed staging candidates below a directory.

    Symbolic links, junctions, previous-publication backups, and already
    quarantined trees are not traversed. Discovery and every returned diagnosis
    are read-only; in particular, no lock file is opened.

    Parameters
    ----------
    root : str or pathlib.Path
        Existing real directory to search. If it is itself a managed staging
        candidate, only that directory is inspected.

    Returns
    -------
    tuple of StagedRunInspection
        Diagnoses sorted by absolute staging path.

    Raises
    ------
    ValueError
        If ``root`` is a symbolic link or junction.
    FileNotFoundError
        If ``root`` does not exist.
    NotADirectoryError
        If ``root`` is not a directory.
    """
    requested_root = _absolute_without_resolving(root)
    if _is_link_or_junction(requested_root):
        raise ValueError(
            f"Inventory root is a symbolic link or junction: {requested_root}"
        )
    if not requested_root.exists():
        raise FileNotFoundError(f"Inventory root does not exist: {requested_root}")
    if not requested_root.is_dir():
        raise NotADirectoryError(f"Inventory root is not a directory: {requested_root}")
    search_root = requested_root.resolve()
    if search_root.name.startswith((".pyages-prev-", ".pyages-quarantine-")):
        return ()
    if _is_staging_directory_name(search_root.name):
        return (inspect_staged_result_run(search_root),)
    return tuple(
        _inspect_discovered_candidate(candidate)
        for candidate in _discover_staging_candidates(search_root)
    )


def _assert_no_nested_staged_runs(
    tree_directory: Path,
) -> None:
    """Refuse a tree containing any reserved nested staging entry."""
    if not _path_entry_exists(tree_directory):
        return
    entries = _strict_tree_entries(tree_directory)
    for candidate, _kind in entries:
        if _is_staging_directory_name(candidate.name):
            raise RuntimeError(
                "Result tree contains an active nested staged run or invalid "
                "staging candidate; refusing to replace "
                f"{tree_directory}: {candidate}."
            )


__all__ = [
    "_assert_no_nested_staged_runs",
    "_is_staging_directory_name",
    "_read_run_state",
    "_RUN_STATE_SCHEMA_VERSION",
    "inspect_staged_result_run",
    "inventory_staged_result_runs",
]
