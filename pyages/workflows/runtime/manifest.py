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
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
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
class StagedRunInspection:
    """Read-only diagnosis of one managed staging-directory candidate.

    Status fields use explicit strings so command-line and Python callers can
    distinguish missing evidence from evidence that was checked and found
    inconsistent. ``promotable_now`` is only a point-in-time diagnosis; promotion
    performs every safety check again under the hierarchy lock.
    """

    stage_directory: Path
    journal_status: Literal["valid", "missing", "invalid"]
    run_id: str | None
    started_at_utc: str | None
    result_directory: Path | None
    manifest_status: Literal["not_checked", "absent", "unsealed", "sealed", "invalid"]
    artifacts_status: Literal["not_checked", "match", "mismatch"]
    publication_status: Literal["not_checked", "current", "changed"]
    promotable_now: bool
    issues: tuple[str, ...]


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


def _absolute_without_resolving(path: str | Path) -> Path:
    """Return an absolute path without hiding a final link or junction."""
    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_junction(path: Path) -> bool:
    """Return whether the final path component redirects to another location."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _path_entry_exists(path: Path) -> bool:
    """Return whether a directory entry exists, including a dangling link."""
    return os.path.lexists(path)


def _lstat_regular_file(path: Path, *, label: str) -> os.stat_result:
    """Validate that ``path`` names one real regular file without redirection."""
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or _is_link_or_junction(path):
        raise RuntimeError(f"{label} is a symbolic link or junction: {path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{label} is not a regular file: {path}")
    return metadata


def _open_strict_regular_file(path: Path, *, label: str) -> tuple[int, os.stat_result]:
    """Open a regular file without following a final symbolic link."""
    before = _lstat_regular_file(path, label=label)
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if _is_link_or_junction(path):
            raise RuntimeError(
                f"{label} is a symbolic link or junction: {path}"
            ) from error
        raise
    try:
        opened = os.fstat(descriptor)
        current = _lstat_regular_file(path, label=label)
        if not stat.S_ISREG(opened.st_mode) or not (
            os.path.samestat(before, opened) and os.path.samestat(current, opened)
        ):
            raise RuntimeError(f"{label} changed while it was being opened: {path}")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, opened


def _validate_open_file_unchanged(
    path: Path,
    *,
    label: str,
    opened: os.stat_result,
    descriptor: int,
) -> None:
    """Reject replacement or mutation of a strictly opened regular file."""
    final_descriptor = os.fstat(descriptor)
    final_path = _lstat_regular_file(path, label=label)
    if not (
        os.path.samestat(opened, final_descriptor)
        and os.path.samestat(final_path, final_descriptor)
    ):
        raise RuntimeError(f"{label} changed while it was being read: {path}")
    stable_fields = ("st_size", "st_mtime_ns", "st_ctime_ns")
    if any(
        getattr(opened, field, None) != getattr(final_descriptor, field, None)
        for field in stable_fields
    ):
        raise RuntimeError(f"{label} changed while it was being read: {path}")


def _read_strict_regular_file(path: Path, *, label: str) -> bytes:
    """Read a real regular file and reject replacement during the read."""
    descriptor, opened = _open_strict_regular_file(path, label=label)
    try:
        chunks: list[bytes] = []
        while block := os.read(descriptor, 1024 * 1024):
            chunks.append(block)
        _validate_open_file_unchanged(
            path,
            label=label,
            opened=opened,
            descriptor=descriptor,
        )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _sha256_strict_regular_file(path: Path, *, label: str) -> str:
    """Hash a real regular file and reject replacement during the read."""
    descriptor, opened = _open_strict_regular_file(path, label=label)
    digest = hashlib.sha256()
    try:
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
        _validate_open_file_unchanged(
            path,
            label=label,
            opened=opened,
            descriptor=descriptor,
        )
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _raise_walk_error(error: OSError) -> None:
    """Make an incomplete filesystem inventory fail explicitly."""
    raise error


def _strict_tree_entries(
    directory: Path,
) -> tuple[tuple[Path, Literal["directory", "file"]], ...]:
    """Inventory a real tree without following or tolerating redirected entries."""
    if _is_link_or_junction(directory):
        raise RuntimeError(
            f"Result tree root is a symbolic link or junction: {directory}"
        )
    root_metadata = os.lstat(directory)
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(f"Result tree root is not a real directory: {directory}")

    entries: list[tuple[Path, Literal["directory", "file"]]] = []
    for current, directory_names, filenames in os.walk(
        directory,
        topdown=True,
        onerror=_raise_walk_error,
        followlinks=False,
    ):
        directory_names.sort()
        filenames.sort()
        current_path = Path(current)
        for name, expected_kind in (
            *((name, "directory") for name in directory_names),
            *((name, "file") for name in filenames),
        ):
            entry = current_path / name
            metadata = os.lstat(entry)
            if stat.S_ISLNK(metadata.st_mode) or _is_link_or_junction(entry):
                raise RuntimeError(
                    f"Result tree contains a symbolic link or junction: {entry}"
                )
            actual_kind = (
                "directory"
                if stat.S_ISDIR(metadata.st_mode)
                else "file"
                if stat.S_ISREG(metadata.st_mode)
                else None
            )
            if actual_kind != expected_kind:
                raise RuntimeError(
                    "Result tree entry changed type or is not a regular file or "
                    f"directory: {entry}"
                )
            entries.append((entry, expected_kind))
    return tuple(
        sorted(entries, key=lambda item: item[0].relative_to(directory).as_posix())
    )


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
        for path, kind in _strict_tree_entries(directory)
        if kind == "file" and path not in control_paths
    ]


def _snapshot(directory: Path) -> dict[str, str]:
    """Return content hashes for every non-control artifact in a directory."""
    return {
        path.relative_to(directory).as_posix(): _sha256_strict_regular_file(
            path,
            label="Result artifact",
        )
        for path in _artifact_files(directory)
    }


def _artifacts(directory: Path, state: _RunState) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for path in _artifact_files(directory):
        relative = path.relative_to(directory).as_posix()
        digest = _sha256_strict_regular_file(path, label="Result artifact")
        if state.mode == "in_place" and state.baseline.get(relative) == digest:
            continue
        artifacts[relative] = digest
    return artifacts


def _publication_token(result_directory: Path) -> str:
    """Return a compare-and-swap token for the complete public result tree."""
    if not _path_entry_exists(result_directory):
        return "absent"
    digest = hashlib.sha256()
    for path, kind in _strict_tree_entries(result_directory):
        relative = path.relative_to(result_directory).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        if kind == "directory":
            digest.update(b"directory")
        else:
            digest.update(b"file\0")
            digest.update(
                bytes.fromhex(
                    _sha256_strict_regular_file(
                        path,
                        label="Public result artifact",
                    )
                )
            )
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


def _is_sha256_digest(value: object) -> bool:
    """Return whether ``value`` is one canonical lowercase SHA-256 digest."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validated_baseline(value: object) -> dict[str, str]:
    """Validate a journal baseline without coercing malformed JSON values."""
    if not isinstance(value, dict):
        raise ValueError("baseline must be an object")
    baseline: dict[str, str] = {}
    for relative, digest in value.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError("baseline paths must be non-empty strings")
        portable = PurePosixPath(relative)
        if (
            portable.is_absolute()
            or ".." in portable.parts
            or portable.as_posix() != relative
        ):
            raise ValueError("baseline paths must be normalized relative POSIX paths")
        if not _is_sha256_digest(digest):
            raise ValueError("baseline values must be SHA-256 digests")
        baseline[relative] = digest
    return baseline


def _validated_publication_token(value: object, *, mode: str) -> str | None:
    """Validate the mode-specific compare-and-swap token in a run journal."""
    if mode == "in_place":
        if value is not None:
            raise ValueError("in-place state cannot contain a publication token")
        return None
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
    mode = payload["mode"]
    if payload["status"] != "started" or mode not in {"in_place", "staged"}:
        raise ValueError("unsupported state")
    if payload.get("schema_version") != _RUN_STATE_SCHEMA_VERSION:
        raise ValueError("unsupported state schema")
    baseline = _validated_baseline(payload.get("baseline", {}))
    if mode == "staged" and baseline:
        raise ValueError("staged state cannot contain an in-place baseline")
    return _RunState(
        run_id=_validated_run_id(payload["run_id"]),
        started_at_utc=_validated_started_at_utc(payload["started_at_utc"]),
        mode=mode,
        result_directory=_validated_result_directory(payload["result_directory"]),
        baseline=baseline,
        expected_publication_token=_validated_publication_token(
            payload.get("expected_publication_token"),
            mode=mode,
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
    """Diagnose a terminal seal and artifact inventory."""
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
        _assert_no_nested_staged_runs(stage, allowed_root_run_id=state.run_id)
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


def _assert_no_nested_staged_runs(
    tree_directory: Path,
    *,
    allowed_root_run_id: str | None = None,
) -> None:
    """Refuse a tree containing an active staged run other than its root."""
    if not _path_entry_exists(tree_directory):
        return
    entries = _strict_tree_entries(tree_directory)
    root_directory = tree_directory.resolve()
    for state_path, kind in entries:
        if kind != "file" or state_path.name != _RUN_STATE_FILENAME:
            continue
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


def _validated_quarantine_state(
    requested_stage: Path,
    *,
    expected_run_id: str,
) -> tuple[Path, _RunState]:
    """Validate the exact managed sibling that may be quarantined."""
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
