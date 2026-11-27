# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file fingerprints source, inputs, distributions, and runtime environments.

"""Build deterministic provenance records for workflow result manifests.

Filesystem publication remains in :mod:`pyages.workflows.runtime.manifest`.
This private module owns only read-only hashing and source/environment discovery.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

from pyages import __version__

_DEPENDENCIES = ("numpy", "scipy", "pandas", "matplotlib", "PyYAML", "pydantic")


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
    """Describe the Git revision and exact tracked workspace used by a run.

    The commit identifier alone is insufficient when tracked files have local
    edits.  A binary-diff hash records those edits, while a second hash covers
    the current contents and portable names of every existing tracked file.
    Git status is retained separately so deleted and untracked paths remain
    visible even though they are not part of that tracked-content snapshot.
    """
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
    """Hash input files and assign stable, non-absolute manifest paths.

    Directories are expanded recursively and duplicate resolved files are
    recorded once.  Repository inputs use repository-relative names; external
    inputs are namespaced by their position in ``paths`` so two equal basenames
    cannot silently collide and local absolute paths are not disclosed.
    """
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


__all__ = [
    "_distribution_provenance",
    "_environment",
    "_indexed_files",
    "_portable_path",
    "_repository_provenance",
    "_run_git",
    "_sha256",
    "_source_repository",
]
