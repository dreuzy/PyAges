# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file stages, verifies, and atomically publishes workflow result directories.

"""Manage workflow results as transaction-like directories with provenance.

A workflow writes into a private staging directory beside its public result.
The run journal binds that stage to a unique identifier, its intended public
path, and the exact public-tree state observed when the run began. On terminal
success or failure, a sealed manifest records input and artifact hashes together
with Python, dependency, package, and repository information.

Publication revalidates the journal, manifest, artifacts, and original public
state while holding a hierarchy lock. Same-filesystem renames then provide the
commit point and permit rollback if replacement fails. Read-only inspection and
explicit quarantine APIs expose interrupted stages without treating incomplete
work as a published result.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import uuid
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, Literal, Mapping

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from pyages import __version__
from pyages.workflows.runtime._manifest_artifacts import (
    _RUN_STATE_FILENAME,
    _TERMINAL_MANIFEST_FILENAME,
    _artifacts,
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
    read_strict_regular_file as _read_strict_regular_file,
)
from pyages.workflows.runtime._manifest_fs import (
    sha256_strict_regular_file as _sha256_strict_regular_file,
)
from pyages.workflows.runtime._manifest_inspection import (
    _RUN_STATE_SCHEMA_VERSION,
    _assert_no_nested_staged_runs,
    _read_run_state,
    inspect_staged_result_run,
    inventory_staged_result_runs,
)
from pyages.workflows.runtime._manifest_provenance import (
    _distribution_provenance,
    _environment,
    _indexed_files,
    _portable_path,
    _repository_provenance,
    _sha256,
    _source_repository,
)
from pyages.workflows.runtime._manifest_types import (
    ResultRun,
    StagedRunInspection,
)
from pyages.workflows.runtime._manifest_types import (
    RunState as _RunState,
)
from pyages.workflows.runtime._manifest_types import (
    new_result_run as _new_result_run,
)

RESULT_SCHEMA_VERSION = 2
_PROMOTION_LOCK_FILENAME = ".pyages-promotion-v1.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_atomic(target: Path, payload: Mapping[str, Any]) -> Path:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=".pyages-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            )
        temporary_path.replace(target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return target


def _state_payload(
    *,
    run_id: str,
    started_at_utc: str,
    mode: Literal["in_place", "staged"],
    result_directory: Path,
    baseline: Mapping[str, str],
    expected_publication_token: str | None = None,
    terminal_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": _RUN_STATE_SCHEMA_VERSION,
        "status": "started",
        "run_id": run_id,
        "started_at_utc": started_at_utc,
        "mode": mode,
        "result_directory": str(result_directory),
        "baseline": dict(baseline),
        "expected_publication_token": expected_publication_token,
        "terminal_manifest_sha256": terminal_manifest_sha256,
    }


def begin_result_run(directory: str | Path) -> Path:
    """Begin a legacy in-place run and invalidate its terminal marker.

    Public workflows use :func:`begin_staged_result_run` so their artifacts can
    be promoted as one isolated result tree. This internal compatibility helper
    exists only for legacy callers that still write directly into a result root.
    """
    output_directory = Path(directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / _TERMINAL_MANIFEST_FILENAME).unlink(missing_ok=True)
    (output_directory / _RUN_STATE_FILENAME).unlink(missing_ok=True)
    run_id = str(uuid.uuid4())
    started_at_utc = _utc_now()
    _write_json_atomic(
        output_directory / _RUN_STATE_FILENAME,
        _state_payload(
            run_id=run_id,
            started_at_utc=started_at_utc,
            mode="in_place",
            result_directory=output_directory,
            baseline=_snapshot(output_directory),
            expected_publication_token=None,
        ),
    )
    return output_directory


def begin_staged_result_run(directory: str | Path) -> ResultRun:
    """Begin an isolated, compare-and-swap protected workflow run.

    The returned handle owns an internal sibling working directory. The current
    public result tree is left untouched, and its complete-tree identity is
    captured under the global hierarchy lock. Write artifacts only below
    ``working_directory``, write a terminal manifest with this handle's
    ``run_id``, then pass the same handle to :func:`promote_result_run`.

    A non-terminal exception deliberately leaves the staging directory and its
    ``started`` journal available for inspection. The handle is opaque and must
    not be constructed or altered by callers.

    Raises
    ------
    ValueError
        If the destination resolves to a filesystem root or its final component
        is a symbolic link or junction.
    NotADirectoryError
        If an existing destination is not a directory.
    OSError
        If the hierarchy lock or isolated working tree cannot be created.
    RuntimeError
        If the process-wide hierarchy lock cannot be acquired.
    """
    requested_result_directory = Path(directory)
    if _is_link_or_junction(requested_result_directory):
        raise ValueError(
            "A symbolic link or junction cannot be used as a result directory."
        )
    result_directory = requested_result_directory.resolve()
    if result_directory == result_directory.parent:
        raise ValueError("A filesystem root cannot be used as a result directory.")
    run_id = str(uuid.uuid4())
    started_at_utc = _utc_now()
    with _promotion_lock(result_directory, run_id):
        # Parent creation can itself mutate an ancestor result tree, so it is
        # covered by the same global hierarchy lock as token capture/promotion.
        result_directory.parent.mkdir(parents=True, exist_ok=True)
        if result_directory.exists() and not result_directory.is_dir():
            raise NotADirectoryError(
                f"Result path is not a directory: {result_directory}"
            )
        if result_directory.is_symlink():
            raise ValueError("A symbolic link cannot be used as a result directory.")

        expected_publication_token = _publication_token(result_directory)
        # Keep the staging component short enough for deeply nested Windows result
        # layouts; the complete UUID remains authoritative in the state journal.
        working_directory = result_directory.parent / f".pyages-{run_id[:12]}"
        working_directory.mkdir(exist_ok=False)
        try:
            _write_json_atomic(
                working_directory / _RUN_STATE_FILENAME,
                _state_payload(
                    run_id=run_id,
                    started_at_utc=started_at_utc,
                    mode="staged",
                    result_directory=result_directory,
                    baseline={},
                    expected_publication_token=expected_publication_token,
                ),
            )
        except BaseException:
            try:
                working_directory.rmdir()
            except OSError:
                pass
            raise
    return _new_result_run(
        run_id=run_id,
        started_at_utc=started_at_utc,
        result_directory=result_directory,
        working_directory=working_directory,
        expected_publication_token=expected_publication_token,
    )


def _resolved_run_state(directory: Path, expected_run_id: str | None) -> _RunState:
    state = _read_run_state(directory)
    if state is None:
        if expected_run_id is not None:
            raise RuntimeError(
                f"Run {expected_run_id} has no active state in {directory}."
            )
        return _RunState(
            run_id=str(uuid.uuid4()),
            started_at_utc=_utc_now(),
            mode="implicit",
            result_directory=directory,
            baseline={},
            expected_publication_token=None,
            terminal_manifest_sha256=None,
            managed=False,
        )
    if expected_run_id is not None and state.run_id != expected_run_id:
        raise RuntimeError(
            f"Run identity mismatch in {directory}: expected {expected_run_id}, "
            f"found {state.run_id}."
        )
    return state


def _manifest_payload(
    directory: str | Path,
    *,
    status: Literal["complete", "failed"],
    workflow: str,
    config_path: str | Path,
    input_paths: Iterable[str | Path] = (),
    details: Mapping[str, Any] | None = None,
    failure: Mapping[str, str] | None = None,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any], _RunState]:
    """Build the common provenance payload for one terminal run state."""
    output_directory = Path(directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    state = _resolved_run_state(output_directory, run_id)
    config = Path(config_path).resolve()
    if not config.is_file():
        raise FileNotFoundError(f"Cannot manifest missing configuration: {config}")
    source_path = Path(__file__).resolve()
    repository = _source_repository(source_path)
    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": status,
        "run_id": state.run_id,
        "started_at_utc": state.started_at_utc,
        "created_at_utc": _utc_now(),
        "pyages_version": __version__,
        "workflow": workflow,
        "command": [str(value) for value in sys.argv],
        "configuration": {
            "path": _portable_path(config, repository),
            "sha256": _sha256(config),
        },
        "inputs": _indexed_files(input_paths, repository),
        "environment": _environment(),
        "package": _distribution_provenance(from_worktree=repository is not None),
        "repository": _repository_provenance(repository),
        "artifacts_sha256": _artifacts(output_directory, state),
    }
    if details:
        payload["details"] = dict(details)
    if failure:
        payload["failure"] = dict(failure)
    return output_directory, payload, state


def _assert_active_run(output_directory: Path, state: _RunState) -> None:
    if not state.managed:
        return
    current = _read_run_state(output_directory)
    if current is None or current.run_id != state.run_id:
        raise RuntimeError(
            f"Run {state.run_id} is no longer active in {output_directory}."
        )


def _write_manifest(
    output_directory: Path,
    payload: Mapping[str, Any],
    state: _RunState,
) -> Path:
    """Atomically replace the terminal manifest for a workflow run."""
    _assert_active_run(output_directory, state)
    target = _write_json_atomic(
        output_directory / _TERMINAL_MANIFEST_FILENAME,
        payload,
    )
    if state.mode == "staged":
        _assert_active_run(output_directory, state)
        _write_json_atomic(
            output_directory / _RUN_STATE_FILENAME,
            _state_payload(
                run_id=state.run_id,
                started_at_utc=state.started_at_utc,
                mode="staged",
                result_directory=state.result_directory,
                baseline=state.baseline,
                expected_publication_token=state.expected_publication_token,
                terminal_manifest_sha256=_sha256_strict_regular_file(
                    target,
                    label="Terminal manifest",
                ),
            ),
        )
    elif state.mode == "in_place":
        _assert_active_run(output_directory, state)
        (output_directory / _RUN_STATE_FILENAME).unlink(missing_ok=True)
    return target


def write_result_manifest(
    directory: str | Path,
    *,
    workflow: str,
    config_path: str | Path,
    input_paths: Iterable[str | Path] = (),
    details: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> Path:
    """Write complete provenance after a workflow succeeds.

    For an isolated run, pass ``run.working_directory`` as ``directory`` and
    ``run.run_id`` as ``run_id``. The resulting terminal manifest must be
    written before the unchanged handle is passed to
    :func:`promote_result_run`.

    Parameters
    ----------
    directory : str or pathlib.Path
        Directory containing the artifacts produced by this run.
    workflow : str
        Stable workflow identifier recorded in the manifest.
    config_path : str or pathlib.Path
        Existing configuration file whose content is fingerprinted.
    input_paths : iterable of str or pathlib.Path, default=()
        Existing input files or directories to inventory and fingerprint.
    details : mapping, optional
        Workflow-specific, JSON-serializable provenance fields.
    run_id : str, optional
        Identity of the staged or managed in-place run. For a staged run this
        must be exactly ``run.run_id``.

    Returns
    -------
    pathlib.Path
        Path of the atomically written ``result_manifest.json`` file.

    Raises
    ------
    FileNotFoundError
        If the configuration or an input path does not exist.
    RuntimeError
        If ``run_id`` does not identify the active run in ``directory``.
    """
    output_directory, payload, state = _manifest_payload(
        directory,
        status="complete",
        workflow=workflow,
        config_path=config_path,
        input_paths=input_paths,
        details=details,
        run_id=run_id,
    )
    return _write_manifest(output_directory, payload, state)


def write_failure_manifest(
    directory: str | Path,
    *,
    workflow: str,
    config_path: str | Path,
    error: BaseException,
    input_paths: Iterable[str | Path] = (),
    details: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> Path:
    """Write provenance for a completed calculation rejected by its gate.

    This is a terminal scientific rejection, not a generic exception logger.
    For an isolated run, pass ``run.working_directory`` as ``directory`` and
    ``run.run_id`` as ``run_id`` before promoting the unchanged handle.

    Parameters
    ----------
    directory : str or pathlib.Path
        Directory containing the evidence preserved for the rejected run.
    workflow : str
        Stable workflow identifier recorded in the manifest.
    config_path : str or pathlib.Path
        Existing configuration file whose content is fingerprinted.
    error : BaseException
        Scientific gate error whose type and message are recorded.
    input_paths : iterable of str or pathlib.Path, default=()
        Existing input files or directories to inventory and fingerprint.
    details : mapping, optional
        Workflow-specific, JSON-serializable provenance fields.
    run_id : str, optional
        Identity of the staged or managed in-place run. For a staged run this
        must be exactly ``run.run_id``.

    Returns
    -------
    pathlib.Path
        Path of the atomically written ``result_manifest.json`` file.

    Raises
    ------
    FileNotFoundError
        If the configuration or an input path does not exist.
    RuntimeError
        If ``run_id`` does not identify the active run in ``directory``.
    """
    output_directory, payload, state = _manifest_payload(
        directory,
        status="failed",
        workflow=workflow,
        config_path=config_path,
        input_paths=input_paths,
        details=details,
        failure={"type": type(error).__name__, "message": str(error)},
        run_id=run_id,
    )
    return _write_manifest(output_directory, payload, state)


def _resolved_promotion_path(path: Path, *, label: str) -> Path:
    """Resolve one promotion path after rejecting final-component redirects."""
    if _is_link_or_junction(path):
        raise RuntimeError(f"{label} path is a symbolic link or junction: {path}")
    return path.resolve()


def _validated_staged_directories(run: ResultRun) -> tuple[Path, Path]:
    """Validate every durable claim needed to promote a staged run.

    The opaque handle must still identify the managed sibling paths and active
    journal.  The terminal manifest must match its journal seal and identify
    the same run, and a fresh artifact inventory must match the manifest.  The
    caller performs the public-tree compare-and-swap check while holding the
    hierarchy lock.
    """
    # Establish the path relationship before trusting any data read from the
    # staging tree or its journal.
    working_directory = _resolved_promotion_path(
        run.working_directory,
        label="Staged working",
    )
    result_directory = _resolved_promotion_path(
        run.result_directory,
        label="Public result",
    )
    if result_directory.exists() and not result_directory.is_dir():
        raise RuntimeError(
            f"Public result target is not a real directory: {result_directory}"
        )
    expected_working_name = f".pyages-{run.run_id[:12]}"
    if (
        result_directory == result_directory.parent
        or working_directory.parent != result_directory.parent
        or working_directory.name != expected_working_name
    ):
        raise RuntimeError("Staged and public result paths do not form a safe pair.")
    # Bind the caller's opaque handle to the persisted staging journal,
    # including the public-tree token captured when the run began.
    state = _read_run_state(working_directory)
    if (
        state is None
        or state.mode != "staged"
        or state.run_id != run.run_id
        or state.result_directory != result_directory
        or state.expected_publication_token != run._expected_publication_token
    ):
        raise RuntimeError(f"Cannot promote an invalid staged run: {working_directory}")
    # A terminal manifest is usable only if its exact bytes match the digest
    # sealed into the journal for this run.
    manifest_path = working_directory / _TERMINAL_MANIFEST_FILENAME
    if not _path_entry_exists(manifest_path):
        raise RuntimeError(f"Cannot promote a non-terminal run: {working_directory}")
    manifest_bytes = _read_strict_regular_file(
        manifest_path,
        label="Sealed terminal manifest",
    )
    if (
        state.terminal_manifest_sha256 is None
        or hashlib.sha256(manifest_bytes).hexdigest() != state.terminal_manifest_sha256
    ):
        raise RuntimeError(
            f"Terminal manifest changed after it was sealed for run {run.run_id}."
        )
    try:
        terminal_payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid terminal manifest: {manifest_path}") from error
    if terminal_payload.get("run_id") != run.run_id or terminal_payload.get(
        "status"
    ) not in {"complete", "failed"}:
        raise RuntimeError(f"Terminal manifest does not match run {run.run_id}.")
    # Rehash the tree last, after the manifest has proved its identity.  This
    # detects outputs changed or added after terminal state was recorded.
    expected_artifacts = terminal_payload.get("artifacts_sha256")
    actual_artifacts = _snapshot(working_directory)
    if expected_artifacts != actual_artifacts:
        raise RuntimeError(
            f"Staged artifacts changed after terminal manifest for run {run.run_id}."
        )
    return working_directory, result_directory


def _validate_private_lock_directory(directory: Path) -> os.stat_result:
    """Validate the real, user-private directory containing the hierarchy lock."""
    metadata = os.lstat(directory)
    if stat.S_ISLNK(metadata.st_mode) or _is_link_or_junction(directory):
        raise RuntimeError(
            f"Promotion lock directory is a symbolic link or junction: {directory}"
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError(f"Promotion lock directory is not a directory: {directory}")
    getuid = getattr(os, "getuid", None)
    if getuid is not None:
        if metadata.st_uid != getuid():
            raise RuntimeError(
                f"Promotion lock directory is not owned by this user: {directory}"
            )
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RuntimeError(
                f"Promotion lock directory is not private (mode 0700): {directory}"
            )
    return metadata


def _promotion_lock_path() -> Path:
    """Return the process-independent lock in a real user-private directory."""
    user_suffix = f"-{os.getuid()}" if getattr(os, "getuid", None) is not None else ""
    lock_directory = Path(tempfile.gettempdir()) / f".pyages-locks-v1{user_suffix}"
    try:
        lock_directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    _validate_private_lock_directory(lock_directory)
    return lock_directory / _PROMOTION_LOCK_FILENAME


def _validate_opened_promotion_lock(
    lock_path: Path,
    *,
    descriptor: int,
    parent_before: os.stat_result,
) -> None:
    """Validate an opened lock and its containing directory before any write."""
    opened = os.fstat(descriptor)
    current = os.lstat(lock_path)
    parent_after = _validate_private_lock_directory(lock_path.parent)
    if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(opened, current):
        raise RuntimeError(f"Promotion lock is not a stable regular file: {lock_path}")
    if not os.path.samestat(parent_before, parent_after):
        raise RuntimeError(
            f"Promotion lock directory changed while opening: {lock_path.parent}"
        )
    if opened.st_nlink != 1:
        raise RuntimeError(f"Promotion lock has filesystem aliases: {lock_path}")
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return
    if opened.st_uid != getuid():
        raise RuntimeError(f"Promotion lock is not owned by this user: {lock_path}")
    if stat.S_IMODE(opened.st_mode) & 0o077:
        raise RuntimeError(f"Promotion lock is not private (mode 0600): {lock_path}")


def _open_secure_promotion_lock(lock_path: Path) -> BinaryIO:
    """Open the hierarchy lock without following a link or accepting aliases."""
    parent_before = _validate_private_lock_directory(lock_path.parent)
    if _path_entry_exists(lock_path) and _is_link_or_junction(lock_path):
        raise RuntimeError(
            f"Promotion lock is a symbolic link or junction: {lock_path}"
        )
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        if _is_link_or_junction(lock_path):
            raise RuntimeError(
                f"Promotion lock is a symbolic link or junction: {lock_path}"
            ) from error
        raise
    try:
        _validate_opened_promotion_lock(
            lock_path,
            descriptor=descriptor,
            parent_before=parent_before,
        )
        return os.fdopen(descriptor, "r+b", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


def _acquire_windows_promotion_lock(stream: BinaryIO) -> None:
    """Retry Windows lock contention until the one-byte lock is acquired."""
    while True:
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EAGAIN} and getattr(
                error, "winerror", None
            ) not in {33, 36}:
                raise
            time.sleep(0.05)
        else:
            return


def _acquire_promotion_lock(stream: BinaryIO) -> None:
    """Acquire the platform's blocking one-byte advisory file lock."""
    stream.seek(0)
    if os.name == "nt":
        _acquire_windows_promotion_lock(stream)
    else:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)


def _release_promotion_lock(stream: BinaryIO) -> None:
    """Release a lock acquired by :func:`_acquire_promotion_lock`."""
    stream.seek(0)
    if os.name == "nt":
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _promotion_lock(result_directory: Path, run_id: str) -> Iterator[None]:
    """Serialize staging creation and promotion, including nested targets."""
    lock_path = _promotion_lock_path()
    stream = _open_secure_promotion_lock(lock_path)
    try:
        _acquire_promotion_lock(stream)
    except OSError as exc:
        stream.close()
        raise RuntimeError(
            f"Could not acquire the promotion lock for {result_directory}: {lock_path}"
        ) from exc
    try:
        stream.seek(0)
        stream.truncate()
        stream.write(f"{run_id}\n".encode("utf-8"))
        stream.flush()
        yield
    finally:
        try:
            _release_promotion_lock(stream)
        except OSError as error:
            warnings.warn(
                f"Could not release promotion lock {lock_path}: {error}",
                RuntimeWarning,
                stacklevel=2,
            )
        finally:
            stream.close()


def _remove_promoted_state(result_directory: Path, run_id: str) -> None:
    """Best-effort removal of the non-terminal staging journal after commit."""
    try:
        (result_directory / _RUN_STATE_FILENAME).unlink(missing_ok=True)
    except OSError as error:
        warnings.warn(
            f"Promoted run {run_id}, but could not remove its state journal: {error}",
            RuntimeWarning,
            stacklevel=2,
        )


def _rollback_failed_promotion(
    *,
    working_directory: Path,
    result_directory: Path,
    backup: Path,
    had_previous: bool,
    promotion_error: BaseException,
) -> None:
    """Restore the pre-promotion namespace after either rename reports failure."""
    try:
        if backup.exists():
            if result_directory.exists():
                if working_directory.exists():
                    raise RuntimeError(
                        "Both the staging and public paths exist after a failed "
                        "promotion."
                    )
                result_directory.replace(working_directory)
            if result_directory.exists():
                raise RuntimeError(
                    "The public result path is occupied during rollback."
                )
            backup.replace(result_directory)
        elif had_previous:
            if not result_directory.exists():
                raise RuntimeError(
                    "The previous publication is missing from both its public "
                    "and backup paths."
                )
        elif result_directory.exists():
            if working_directory.exists():
                raise RuntimeError(
                    "Both the staging and public paths exist after a failed promotion."
                )
            result_directory.replace(working_directory)
    except BaseException as rollback_error:
        raise RuntimeError(
            "Promotion failed and rollback could not restore the previous "
            f"namespace. public={result_directory}; staging={working_directory}; "
            f"backup={backup}; original_error={promotion_error!r}; "
            f"rollback_error={rollback_error!r}"
        ) from rollback_error


def promote_result_run(run: ResultRun) -> Path:
    """Publish a terminal staged tree over its exact predecessor.

    Promotion holds the global hierarchy lock, validates the opaque handle and
    terminal manifest, rehashes every staged artifact, rejects a changed public
    tree or active nested staging area, and then performs same-filesystem
    renames. The successful working-tree-to-result rename is the commit point.
    If either rename reports failure, restoration is attempted before the
    original error is propagated. A failed restoration raises an explicit
    error containing the public, staging, and backup recovery paths. Journal
    and backup cleanup after commit are best effort and cannot turn a
    publication back into a failed run.

    Returns
    -------
    Path
        The resolved public result directory.

    Raises
    ------
    TypeError
        If ``run`` is not a handle returned by :func:`begin_staged_result_run`.
    RuntimeError
        If a path redirects through a link or junction; run identity, manifest,
        artifacts, nesting, or the CAS token no longer matches the state
        captured by :func:`begin_staged_result_run`; or rollback cannot restore
        the pre-promotion namespace.
    OSError
        If the lock file cannot be opened or a required filesystem rename fails.
    """
    if not isinstance(run, ResultRun):
        raise TypeError(
            "promote_result_run() requires a ResultRun handle returned by "
            "begin_staged_result_run()."
        )
    _resolved_promotion_path(run.working_directory, label="Staged working")
    result_directory = _resolved_promotion_path(
        run.result_directory,
        label="Public result",
    )
    with _promotion_lock(result_directory, run.run_id):
        # Revalidate all durable evidence under the hierarchy lock, then apply
        # the publication token as a compare-and-swap guard on the public tree.
        working_directory, result_directory = _validated_staged_directories(run)
        current_token = _publication_token(result_directory)
        if current_token != run._expected_publication_token:
            raise RuntimeError(
                "Public result changed after this run started; refusing to replace "
                f"{result_directory}."
            )
        _assert_no_nested_staged_runs(result_directory)
        _assert_no_nested_staged_runs(
            working_directory,
            allowed_root_run_id=run.run_id,
        )
        # Recheck after acquiring the lock so no late artifact can be published
        # under the already-written terminal manifest.
        _validated_staged_directories(run)
        backup = result_directory.parent / f".pyages-prev-{run.run_id[:12]}"
        if backup.exists():
            raise FileExistsError(f"Promotion backup already exists: {backup}")
        # Both namespace changes share one rollback boundary. If a platform
        # reports an error after completing a rename, filesystem state decides
        # which inverse renames are required.
        had_previous = result_directory.exists()
        try:
            if had_previous:
                result_directory.replace(backup)
            working_directory.replace(result_directory)
        except BaseException as promotion_error:
            _rollback_failed_promotion(
                working_directory=working_directory,
                result_directory=result_directory,
                backup=backup,
                had_previous=had_previous,
                promotion_error=promotion_error,
            )
            raise

        _remove_promoted_state(result_directory, run.run_id)
        if had_previous:
            try:
                shutil.rmtree(backup)
            except OSError as error:
                warnings.warn(
                    f"Promoted run {run.run_id}, but could not remove backup "
                    f"{backup}: {error}",
                    RuntimeWarning,
                    stacklevel=2,
                )
    return result_directory


def _validated_quarantine_state(
    requested_stage: Path,
    *,
    expected_run_id: str,
) -> tuple[Path, _RunState]:
    """Validate the exact managed staging tree that may be quarantined.

    Quarantine is allowed only for a real directory whose active journal has
    the fully acknowledged run identifier and whose name and parent still form
    the managed sibling pair with the public result.  This prevents an operator
    typo or redirected path from moving an unrelated tree.
    """
    if _is_link_or_junction(requested_stage):
        raise RuntimeError(
            f"Staging path is a symbolic link or junction: {requested_stage}"
        )
    stage = requested_stage.resolve(strict=True)
    if not stage.is_dir():
        raise NotADirectoryError(f"Staging path is not a directory: {stage}")
    state = _read_run_state(stage)
    if state is None or state.mode != "staged":
        raise RuntimeError(f"No valid managed staged journal in {stage}.")
    if state.run_id != expected_run_id:
        raise RuntimeError(
            f"Run identity mismatch in {stage}: expected {expected_run_id}, "
            f"found {state.run_id}."
        )
    if _is_link_or_junction(state.result_directory):
        raise RuntimeError(
            f"Public result path is a symbolic link or junction: {state.result_directory}"
        )
    if (
        _path_entry_exists(state.result_directory)
        and not state.result_directory.is_dir()
    ):
        raise RuntimeError(
            f"Public result path is not a real directory: {state.result_directory}"
        )
    if state.result_directory == state.result_directory.parent or (
        stage.parent != state.result_directory.parent
        or stage.name != f".pyages-{state.run_id[:12]}"
    ):
        raise RuntimeError(
            "Staging and public result paths do not form a safe managed pair."
        )
    return stage, state


def quarantine_staged_result_run(
    stage_directory: str | Path,
    *,
    run_id: str,
) -> Path:
    """Quarantine one explicitly acknowledged managed staging tree.

    The complete tree is atomically renamed to a sibling whose name starts
    with ``.pyages-quarantine-``. Nothing is deleted. The operator must first
    stop or otherwise exclude any process that may still write to the stage;
    the hierarchy lock coordinates PyAges namespace transactions but cannot
    prove that workflow computation has stopped.

    The journal and safe sibling relationship are validated before and after
    acquiring the same global hierarchy lock used for creation and promotion.
    The complete UUID is required as an acknowledgement against quarantining
    the wrong candidate.

    Parameters
    ----------
    stage_directory : str or pathlib.Path
        Exact managed staging directory to rename.
    run_id : str
        Complete UUID shown by :func:`inspect_staged_result_run`.

    Returns
    -------
    pathlib.Path
        New sibling path containing the untouched quarantined tree.

    Raises
    ------
    ValueError
        If ``run_id`` is not a complete UUID.
    RuntimeError
        If the path redirects through a link or junction, the journal or
        sibling relationship is invalid, or the UUID does not match.
    FileExistsError
        If the quarantine destination already exists.
    OSError
        If the lock file cannot be opened or the atomic rename fails.
    """
    try:
        acknowledged_run_id = str(uuid.UUID(run_id))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"run_id must be a complete UUID: {run_id!r}") from error
    requested_stage = _absolute_without_resolving(stage_directory)
    stage, state = _validated_quarantine_state(
        requested_stage,
        expected_run_id=acknowledged_run_id,
    )
    with _promotion_lock(state.result_directory, state.run_id):
        locked_stage, locked_state = _validated_quarantine_state(
            requested_stage,
            expected_run_id=acknowledged_run_id,
        )
        if (
            locked_stage != stage
            or locked_state.result_directory != state.result_directory
        ):
            raise RuntimeError(
                "The staging target changed while quarantine was pending."
            )
        quarantine = stage.parent / f".pyages-quarantine-{state.run_id[:12]}"
        if quarantine.exists() or _is_link_or_junction(quarantine):
            raise FileExistsError(
                f"Quarantine destination already exists: {quarantine}"
            )
        stage.replace(quarantine)
    return quarantine


__all__ = [
    "RESULT_SCHEMA_VERSION",
    "ResultRun",
    "StagedRunInspection",
    "begin_staged_result_run",
    "inspect_staged_result_run",
    "inventory_staged_result_runs",
    "promote_result_run",
    "quarantine_staged_result_run",
    "write_failure_manifest",
    "write_result_manifest",
]
