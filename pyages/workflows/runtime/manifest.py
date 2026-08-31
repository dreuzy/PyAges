# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Versioned provenance manifests for public workflow result directories."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Iterator, Literal, Mapping

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from pyages import __version__

RESULT_SCHEMA_VERSION = 2
_DEPENDENCIES = ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pydantic")
_RUN_STATE_FILENAME = ".pyages-run-state.json"
_TERMINAL_MANIFEST_FILENAME = "result_manifest.json"
_PROMOTION_LOCK_FILENAME = ".pyages-promotion-v1.lock"


@dataclass(frozen=True)
class ResultRun:
    """One isolated workflow run awaiting terminal promotion."""

    run_id: str
    started_at_utc: str
    result_directory: Path
    working_directory: Path
    expected_publication_token: str


@dataclass(frozen=True)
class _RunState:
    run_id: str
    started_at_utc: str
    mode: Literal["implicit", "in_place", "staged"]
    result_directory: Path
    baseline: Mapping[str, str]
    expected_publication_token: str | None
    managed: bool


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    return [
        path
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and path.name not in {_TERMINAL_MANIFEST_FILENAME, _RUN_STATE_FILENAME}
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
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "status": "started",
        "run_id": run_id,
        "started_at_utc": started_at_utc,
        "mode": mode,
        "result_directory": str(result_directory),
        "baseline": dict(baseline),
        "expected_publication_token": expected_publication_token,
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
        if payload.get("schema_version") != 2:
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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Invalid PyAges run state: {state_path}") from error
    return _RunState(
        run_id=run_id,
        started_at_utc=started_at_utc,
        mode=mode,
        result_directory=result_directory,
        baseline=baseline,
        expected_publication_token=expected_publication_token,
        managed=True,
    )


def begin_result_run(directory: str | Path) -> Path:
    """Begin a compatible in-place run and invalidate its terminal marker.

    Public workflows use :func:`begin_staged_result_run` so their artifacts can
    be promoted as one isolated result tree. This function remains available to
    contributor workflows that already write directly into their result root.
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
    """Create an isolated work tree for a public workflow execution."""
    result_directory = Path(directory).resolve()
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
    return ResultRun(
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
    if state.mode == "in_place":
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
    """Write complete provenance after a public workflow succeeds."""
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
    """Write provenance for a completed calculation rejected by its gate."""
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


def _validated_staged_directories(run: ResultRun) -> tuple[Path, Path]:
    """Validate a staged run and return its working and public directories."""
    working_directory = run.working_directory.resolve()
    result_directory = run.result_directory.resolve()
    if result_directory.is_symlink() or (
        result_directory.exists() and not result_directory.is_dir()
    ):
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
        or state.expected_publication_token != run.expected_publication_token
    ):
        raise RuntimeError(f"Cannot promote an invalid staged run: {working_directory}")
    manifest_path = working_directory / _TERMINAL_MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise RuntimeError(f"Cannot promote a non-terminal run: {working_directory}")
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


def _acquire_promotion_lock(stream: BinaryIO) -> None:
    """Acquire the platform's blocking one-byte advisory file lock."""
    stream.seek(0)
    if os.name == "nt":
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
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
            f"Another promotion is active for {result_directory}: {lock_path}"
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


def _assert_no_nested_staged_runs(result_directory: Path) -> None:
    """Refuse to replace a tree that contains another run's active staging area."""
    if not result_directory.is_dir():
        return
    for state_path in result_directory.rglob(_RUN_STATE_FILENAME):
        state_directory = state_path.parent.resolve()
        state = _read_run_state(state_directory)
        if (
            state is not None
            and state.mode == "staged"
            and state_directory != state.result_directory
        ):
            raise RuntimeError(
                "Public result contains an active nested staged run; refusing to "
                f"replace {result_directory}: {state_directory}."
            )


def promote_result_run(run: ResultRun) -> Path:
    """Promote one terminal staged tree without mixing it with older artifacts."""
    result_directory = run.result_directory.resolve()
    with _promotion_lock(result_directory, run.run_id):
        working_directory, result_directory = _validated_staged_directories(run)
        current_token = _publication_token(result_directory)
        if current_token != run.expected_publication_token:
            raise RuntimeError(
                "Public result changed after this run started; refusing to replace "
                f"{result_directory}."
            )
        _assert_no_nested_staged_runs(result_directory)
        # Recheck after acquiring the lock so no late artifact can be published
        # under the already-written terminal manifest.
        _validated_staged_directories(run)
        backup = result_directory.parent / f".pyages-prev-{run.run_id[:12]}"
        if backup.exists():
            raise FileExistsError(f"Promotion backup already exists: {backup}")
        moved_previous = False
        if result_directory.exists():
            result_directory.replace(backup)
            moved_previous = True
        try:
            working_directory.replace(result_directory)
        except BaseException:
            if moved_previous and not result_directory.exists():
                backup.replace(result_directory)
            raise

        _remove_promoted_state(result_directory, run.run_id)
        if moved_previous:
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
    "begin_result_run",
    "begin_staged_result_run",
    "promote_result_run",
    "write_failure_manifest",
    "write_result_manifest",
]
