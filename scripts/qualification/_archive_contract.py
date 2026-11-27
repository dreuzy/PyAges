# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Define filesystem and naming invariants for qualification archives.

Qualification archives can be produced on one operating system and verified on
another. This module therefore centralizes portable-path checks, regular-file
traversal, control filenames, deterministic ZIP metadata, and file hashing.
It performs no scientific validation and does not assemble an archive.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from scripts.common.provenance import sha256_file

ARCHIVE_MANIFEST = "QUALIFICATION_ARCHIVE.json"
ARCHIVE_CHECKSUMS = "CHECKSUMS.sha256"
ARCHIVE_README = "README.md"
ARCHIVE_SCHEMA_VERSION = 1
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def safe_portable_path(value: object, *, context: str) -> PurePosixPath:
    """Return a canonical relative POSIX path that is safe on every OS.

    Absolute paths, parent traversal, Windows drives, backslashes, and
    non-canonical spellings are rejected before a path is joined to an
    extraction directory.
    """
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeError(f"Unsafe qualification archive {context}: {value}")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or value != relative.as_posix()
        or any(PureWindowsPath(part).drive for part in relative.parts)
    ):
        raise RuntimeError(f"Unsafe qualification archive {context}: {value}")
    return relative


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of one regular file."""
    return sha256_file(path)


def is_link_or_junction(path: Path) -> bool:
    """Return whether a path is a symbolic link or Windows junction."""
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return path.is_symlink() or bool(is_junction(path))


def regular_files(root: Path) -> list[Path]:
    """List regular files below ``root`` without following filesystem links.

    Rejecting links and non-regular files prevents an input tree from silently
    including content outside the qualified result directory.
    """
    if is_link_or_junction(root):
        raise ValueError(f"Input tree is a symbolic link or junction: {root}")
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            candidate = current_path / name
            if is_link_or_junction(candidate):
                raise ValueError(
                    f"Input tree contains a symbolic link or junction: {candidate}"
                )
        for name in filenames:
            candidate = current_path / name
            if is_link_or_junction(candidate):
                raise ValueError(f"Input tree contains a symbolic link: {candidate}")
            if not candidate.is_file():
                raise ValueError(f"Input tree contains a non-regular file: {candidate}")
            files.append(candidate)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())
