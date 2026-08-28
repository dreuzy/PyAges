# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Versioned provenance manifest for public workflow result directories."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from pyages import __version__

RESULT_SCHEMA_VERSION = 2
_DEPENDENCIES = ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pydantic")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _repository_provenance(repository: Path) -> dict[str, Any]:
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


def _portable_path(path: Path, repository: Path) -> str:
    try:
        return path.relative_to(repository).as_posix()
    except ValueError:
        return path.name


def _indexed_files(
    paths: Iterable[str | Path], repository: Path
) -> list[dict[str, Any]]:
    indexed = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw).resolve()
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = sorted(
                candidate for candidate in path.rglob("*") if candidate.is_file()
            )
        else:
            raise FileNotFoundError(f"Cannot manifest missing input: {path}")
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            indexed.append(
                {
                    "path": _portable_path(resolved, repository),
                    "sha256": _sha256(resolved),
                }
            )
    return indexed


def _artifacts(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): _sha256(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != "result_manifest.json"
    }


def begin_result_run(directory: str | Path) -> Path:
    """Invalidate any previous success marker for a reused result directory."""
    output_directory = Path(directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest = output_directory / "result_manifest.json"
    manifest.unlink(missing_ok=True)
    return output_directory


def write_result_manifest(
    directory: str | Path,
    *,
    workflow: str,
    config_path: str | Path,
    input_paths: Iterable[str | Path] = (),
    details: Mapping[str, Any] | None = None,
) -> Path:
    """Write complete provenance after a public workflow succeeds."""
    output_directory = Path(directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    config = Path(config_path).resolve()
    if not config.is_file():
        raise FileNotFoundError(f"Cannot manifest missing configuration: {config}")
    repository = Path(__file__).resolve().parents[2]
    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pyages_version": __version__,
        "workflow": workflow,
        "command": [str(value) for value in sys.argv],
        "configuration": {
            "path": _portable_path(config, repository),
            "sha256": _sha256(config),
        },
        "inputs": _indexed_files(input_paths, repository),
        "environment": _environment(),
        "repository": _repository_provenance(repository),
        "artifacts_sha256": _artifacts(output_directory),
    }
    if details:
        payload["details"] = dict(details)
    target = output_directory / "result_manifest.json"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_directory,
            prefix=".result_manifest.",
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


__all__ = ["RESULT_SCHEMA_VERSION", "begin_result_run", "write_result_manifest"]
