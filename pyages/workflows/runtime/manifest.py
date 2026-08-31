# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Versioned provenance manifests for public workflow result directories."""

from __future__ import annotations

import errno
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, Literal, Mapping

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from pyages import __version__

RESULT_SCHEMA_VERSION = 2
_RUN_STATE_SCHEMA_VERSION = 3
_DEPENDENCIES = ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pydantic")
_RUN_STATE_FILENAME = ".pyages-run-state.json"
_TERMINAL_MANIFEST_FILENAME = "result_manifest.json"
_PROMOTION_LOCK_FILENAME = ".pyages-promotion-v1.lock"


@dataclass(frozen=True, init=False)
class ResultRun:
    """Opaque handle for a staged run created by :func:`begin_staged_result_run`.

    Callers may use the run identity and resolved directories, but should not
    construct this class themselves. Pass the unchanged handle to
    :func:`promote_result_run` after writing its terminal manifest.
    """

    run_id: str
    started_at_utc: str
    result_directory: Path
    working_directory: Path
    _expected_publication_token: str = field(repr=False)

    def __init__(self) -> None:
        """Reject direct construction; use :func:`begin_staged_result_run`."""
        raise TypeError("ResultRun handles are created by begin_staged_result_run().")


@dataclass(frozen=True)
class _RunState:
    """Validated journal state for implicit, in-place, or isolated staged writes.

    ``implicit`` exists only while writing a compatibility manifest without a
    journal. ``in_place`` tracks contributor workflows that reuse one tree;
    ``staged`` binds an isolated working tree to its public destination and CAS
    token, then seals its terminal manifest digest before promotion. The journal
    schema is independent from ``RESULT_SCHEMA_VERSION``.
    """

    run_id: str
    started_at_utc: str
    mode: Literal["implicit", "in_place", "staged"]
    result_directory: Path
    baseline: Mapping[str, str]
    expected_publication_token: str | None
    terminal_manifest_sha256: str | None
    managed: bool


def _new_result_run(
    *,
    run_id: str,
    started_at_utc: str,
    result_directory: Path,
    working_directory: Path,
    expected_publication_token: str,
) -> ResultRun:
    """Construct the opaque staged-run handle inside this module only."""
    run = object.__new__(ResultRun)
    object.__setattr__(run, "run_id", run_id)
    object.__setattr__(run, "started_at_utc", started_at_utc)
    object.__setattr__(run, "result_directory", result_directory)
    object.__setattr__(run, "working_directory", working_directory)
    object.__setattr__(
        run,
        "_expected_publication_token",
        expected_publication_token,
    )
    return run


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    """Return whether the final path component redirects to another location."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_git(repository: Path, *args: str, binary: bool = False):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repository,
            capture_output=True,
            text=not binary,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def _source_repository(source_path: Path) -> Path | None:
    """Return the worktree that actually tracks the imported source file."""
    top_level = _run_git(source_path.parent, "rev-parse", "--show-toplevel")
    if not isinstance(top_level, str) or not top_level.strip():
        return None
    repository = Path(top_level.strip()).resolve()
    try:
        relative_source = source_path.resolve().relative_to(repository).as_posix()
    except ValueError:
        return None
    tracked = _run_git(
        repository,
        "ls-files",
        "--error-unmatch",
        "--",
        relative_source,
    )
    if not isinstance(tracked, str):
        return None
    tracked_paths = {line.strip().replace("\\", "/") for line in tracked.splitlines()}
    return repository if relative_source in tracked_paths else None


def _empty_repository_provenance() -> dict[str, Any]:
    return {
        "git_head": None,
        "dirty": None,
        "status_porcelain_v2": [],
        "tracked_diff_sha256": None,
        "tracked_workspace_sha256": None,
        "tracked_file_count": 0,
    }


def _repository_provenance(repository: Path | None) -> dict[str, Any]:
    if repository is None:
        return _empty_repository_provenance()
    head = _run_git(repository, "rev-parse", "HEAD")
    status = _run_git(repository, "status", "--porcelain=v2")
    diff = _run_git(repository, "diff", "--binary", "HEAD", binary=True)
    tracked = _run_git(repository, "ls-files", "-z")
    snapshot = hashlib.sha256()
    tracked_count = 0
    if isinstance(tracked, str):
        for raw in sorted(item for item in tracked.split("\0") if item):
            path = repository / raw
            if not path.is_file():
                continue
            tracked_count += 1
            snapshot.update(raw.replace("\\", "/").encode("utf-8"))
            snapshot.update(b"\0")
            snapshot.update(bytes.fromhex(_sha256(path)))
    return {
        "git_head": head.strip() if isinstance(head, str) else None,
        "dirty": bool(status.strip()) if isinstance(status, str) else None,
        "status_porcelain_v2": status.splitlines() if isinstance(status, str) else [],
        "tracked_diff_sha256": (
            hashlib.sha256(diff).hexdigest() if isinstance(diff, bytes) else None
        ),
        "tracked_workspace_sha256": snapshot.hexdigest() if tracked_count else None,
        "tracked_file_count": tracked_count,
    }


def _distribution_provenance(*, from_worktree: bool) -> dict[str, Any]:
    """Fingerprint installed-distribution metadata independently from Git."""
    try:
        distribution = importlib.metadata.distribution("pyages")
    except importlib.metadata.PackageNotFoundError:
        return {
            "name": "pyages",
            "version": __version__,
            "version_matches_runtime": True,
            "source": "git_worktree" if from_worktree else "unknown",
            "direct_url": None,
            "record_sha256": None,
            "record_file_count": 0,
            "metadata_sha256": None,
            "installed_file_count": 0,
        }

    direct_url_text = distribution.read_text("direct_url.json")
    direct_url: Mapping[str, Any] | None = None
    if direct_url_text is not None:
        try:
            parsed = json.loads(direct_url_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            direct_url = parsed

    record = distribution.read_text("RECORD")
    metadata_text = distribution.read_text("METADATA")
    if metadata_text is None:
        metadata_text = distribution.read_text("PKG-INFO")
    files = distribution.files or ()
    return {
        "name": distribution.metadata.get("Name", "pyages"),
        "version": distribution.version,
        "version_matches_runtime": distribution.version == __version__,
        "source": "git_worktree" if from_worktree else "installed_distribution",
        "direct_url": direct_url,
        "record_sha256": _sha256_text(record),
        "record_file_count": (
            sum(bool(line.strip()) for line in record.splitlines()) if record else 0
        ),
        "metadata_sha256": _sha256_text(metadata_text),
        "installed_file_count": len(files),
    }


def _environment() -> dict[str, Any]:
    versions: dict[str, str] = {}
    for dependency in _DEPENDENCIES:
        try:
            versions[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            versions[dependency] = "not-installed"
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "dependencies": versions,
    }


def _portable_path(path: Path, repository: Path | None) -> str:
    if repository is not None:
        try:
            return path.relative_to(repository).as_posix()
        except ValueError:
            pass
    return path.name


def _indexed_files(
    paths: Iterable[str | Path], repository: Path | None
) -> list[dict[str, Any]]:
    indexed = []
    seen: set[Path] = set()
    for root_index, raw in enumerate(paths):
        path = Path(raw).resolve()
        if path.is_file():
            candidates = [(path, Path(path.name))]
        elif path.is_dir():
            candidates = sorted(
                (candidate, candidate.relative_to(path))
                for candidate in path.rglob("*")
                if candidate.is_file()
            )
        else:
            raise FileNotFoundError(f"Cannot manifest missing input: {path}")
        for candidate, relative_to_root in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if repository is not None:
                try:
                    portable_path = resolved.relative_to(repository).as_posix()
                except ValueError:
                    portable_path = (
                        Path("external") / str(root_index) / relative_to_root
                    ).as_posix()
            else:
                portable_path = (
                    Path("external") / str(root_index) / relative_to_root
                ).as_posix()
            indexed.append(
                {
                    "path": portable_path,
                    "sha256": _sha256(resolved),
                }
            )
    return indexed


def _artifact_files(directory: Path) -> list[Path]:
    control_paths = {
        directory / _TERMINAL_MANIFEST_FILENAME,
        directory / _RUN_STATE_FILENAME,
    }
    return [
        path
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path not in control_paths
    ]


def _snapshot(directory: Path) -> dict[str, str]:
    """Return content hashes for every non-control artifact in a directory."""
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in _artifact_files(directory)
    }


def _artifacts(directory: Path, state: _RunState) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for path in _artifact_files(directory):
        relative = path.relative_to(directory).as_posix()
        digest = _sha256(path)
        if state.mode == "in_place" and state.baseline.get(relative) == digest:
            continue
        artifacts[relative] = digest
    return artifacts


def _publication_token(result_directory: Path) -> str:
    """Return a compare-and-swap token for the complete public result tree."""
    if not result_directory.exists():
        return "absent"
    digest = hashlib.sha256()
    for path in sorted(result_directory.rglob("*")):
        relative = path.relative_to(result_directory).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"link\0")
            digest.update(os.readlink(path).encode("utf-8"))
        elif path.is_dir():
            digest.update(b"directory")
        elif path.is_file():
            digest.update(b"file\0")
            digest.update(bytes.fromhex(_sha256(path)))
        else:
            digest.update(b"other")
        digest.update(b"\0")
    return f"tree:{digest.hexdigest()}"


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


def _read_run_state(directory: Path) -> _RunState | None:
    state_path = directory / _RUN_STATE_FILENAME
    if not state_path.is_file():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        run_id = str(uuid.UUID(payload["run_id"]))
        mode = payload["mode"]
        if payload["status"] != "started" or mode not in {"in_place", "staged"}:
            raise ValueError("unsupported state")
        if payload.get("schema_version") != _RUN_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported state schema")
        baseline = {
            str(path): str(digest)
            for path, digest in payload.get("baseline", {}).items()
        }
        result_directory = Path(payload["result_directory"]).resolve()
        started_at_utc = str(payload["started_at_utc"])
        expected_publication_token = payload.get("expected_publication_token")
        if expected_publication_token is not None:
            expected_publication_token = str(expected_publication_token)
        terminal_manifest_sha256 = payload.get("terminal_manifest_sha256")
        if terminal_manifest_sha256 is not None:
            if not isinstance(terminal_manifest_sha256, str) or (
                len(terminal_manifest_sha256) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in terminal_manifest_sha256
                )
            ):
                raise ValueError("invalid terminal manifest digest")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid PyAges run state: {state_path}") from error
    return _RunState(
        run_id=run_id,
        started_at_utc=started_at_utc,
        mode=mode,
        result_directory=result_directory,
        baseline=baseline,
        expected_publication_token=expected_publication_token,
        terminal_manifest_sha256=terminal_manifest_sha256,
        managed=True,
    )


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
                terminal_manifest_sha256=_sha256(target),
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
    """Validate a staged run and return its working and public directories."""
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
    state = _read_run_state(working_directory)
    if (
        state is None
        or state.mode != "staged"
        or state.run_id != run.run_id
        or state.result_directory != result_directory
        or state.expected_publication_token != run._expected_publication_token
    ):
        raise RuntimeError(f"Cannot promote an invalid staged run: {working_directory}")
    manifest_path = working_directory / _TERMINAL_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RuntimeError(f"Cannot promote a non-terminal run: {working_directory}")
    if state.terminal_manifest_sha256 is None or (
        _sha256(manifest_path) != state.terminal_manifest_sha256
    ):
        raise RuntimeError(
            f"Terminal manifest changed after it was sealed for run {run.run_id}."
        )
    try:
        terminal_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid terminal manifest: {manifest_path}") from error
    if terminal_payload.get("run_id") != run.run_id or terminal_payload.get(
        "status"
    ) not in {"complete", "failed"}:
        raise RuntimeError(f"Terminal manifest does not match run {run.run_id}.")
    expected_artifacts = terminal_payload.get("artifacts_sha256")
    actual_artifacts = _snapshot(working_directory)
    if expected_artifacts != actual_artifacts:
        raise RuntimeError(
            f"Staged artifacts changed after terminal manifest for run {run.run_id}."
        )
    return working_directory, result_directory


def _promotion_lock_path() -> Path:
    """Return the process-independent lock shared by all staged result trees."""
    return Path(tempfile.gettempdir()) / _PROMOTION_LOCK_FILENAME


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
    stream = lock_path.open("a+b")
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


def _assert_no_nested_staged_runs(
    tree_directory: Path,
    *,
    allowed_root_run_id: str | None = None,
) -> None:
    """Refuse a tree containing an active staged run other than its root."""
    if not tree_directory.is_dir():
        return
    root_directory = tree_directory.resolve()
    for state_path in tree_directory.rglob(_RUN_STATE_FILENAME):
        state_directory = state_path.parent.resolve()
        try:
            state = _read_run_state(state_directory)
        except RuntimeError:
            # Nested homonyms are ordinary manifested artifacts unless they
            # contain a valid active-run journal.
            continue
        if (
            state_directory == root_directory
            and state is not None
            and state.run_id == allowed_root_run_id
        ):
            continue
        if (
            state is not None
            and state.mode == "staged"
            and state_directory != state.result_directory
        ):
            raise RuntimeError(
                "Result tree contains an active nested staged run; refusing to "
                f"replace {tree_directory}: {state_directory}."
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


__all__ = [
    "RESULT_SCHEMA_VERSION",
    "ResultRun",
    "begin_staged_result_run",
    "promote_result_run",
    "write_failure_manifest",
    "write_result_manifest",
]
