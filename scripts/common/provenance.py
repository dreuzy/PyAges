# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Shared provenance helpers for publication-oriented simulation campaigns."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(root: Path, *args: str, binary: bool = False):
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=not binary,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed while recording scientific provenance"
        )
    return result.stdout


def _snapshot_digest(root: Path, relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        path = root / relative
        if not path.is_file():
            continue
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def repository_provenance(root: Path) -> dict[str, Any]:
    """Identify the complete tracked and untracked source workspace."""
    root = root.resolve()
    head = str(_git(root, "rev-parse", "HEAD")).strip()
    status = str(_git(root, "status", "--porcelain=v2")).splitlines()
    diff = _git(root, "diff", "--binary", "HEAD", binary=True)
    tracked = [
        value for value in str(_git(root, "ls-files", "-z")).split("\0") if value
    ]
    untracked = [
        value
        for value in str(
            _git(root, "ls-files", "--others", "--exclude-standard", "-z")
        ).split("\0")
        if value
    ]
    return {
        "git_head": head,
        "dirty": bool(status),
        "status_porcelain_v2": status,
        "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "tracked_workspace_sha256": _snapshot_digest(root, tracked),
        "tracked_file_count": len(tracked),
        "untracked_workspace_sha256": _snapshot_digest(root, untracked),
        "untracked_file_count": len(untracked),
        "untracked_files_sha256": {
            relative.replace("\\", "/"): sha256_file(root / relative)
            for relative in sorted(untracked)
            if (root / relative).is_file()
        },
    }


__all__ = ["repository_provenance", "sha256_file"]
