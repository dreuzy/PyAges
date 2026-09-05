# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file performs strict filesystem reads for result provenance.

"""Read and inventory result trees without following redirected path entries.

Regular files are opened with platform-appropriate safeguards, checked again
after reading, and rejected if their identity or metadata changed during the
operation. Symbolic links, Windows junctions, special files, and walk errors are
reported instead of being followed or omitted.

The manifest layer uses the returned stable bytes, hashes, and sorted tree
entries to ensure that recorded provenance describes one concrete filesystem
state rather than a mixture observed during concurrent modification.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Literal


def absolute_without_resolving(path: str | Path) -> Path:
    """Return an absolute path without hiding a final link or junction."""
    return Path(os.path.abspath(os.fspath(path)))


def is_link_or_junction(path: Path) -> bool:
    """Return whether the final path component redirects elsewhere."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def path_entry_exists(path: Path) -> bool:
    """Return whether a directory entry exists, including a dangling link."""
    return os.path.lexists(path)


def lstat_regular_file(path: Path, *, label: str) -> os.stat_result:
    """Validate that ``path`` is a real regular file without redirection."""
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or is_link_or_junction(path):
        raise RuntimeError(f"{label} is a symbolic link or junction: {path}")
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"{label} is not a regular file: {path}")
    return metadata


def open_strict_regular_file(path: Path, *, label: str) -> tuple[int, os.stat_result]:
    """Open a regular file without following a final symbolic link."""
    before = lstat_regular_file(path, label=label)
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if is_link_or_junction(path):
            raise RuntimeError(
                f"{label} is a symbolic link or junction: {path}"
            ) from error
        raise
    try:
        opened = os.fstat(descriptor)
        current = lstat_regular_file(path, label=label)
        if not stat.S_ISREG(opened.st_mode) or not (
            os.path.samestat(before, opened) and os.path.samestat(current, opened)
        ):
            raise RuntimeError(f"{label} changed while it was being opened: {path}")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, opened


def validate_open_file_unchanged(
    path: Path,
    *,
    label: str,
    opened: os.stat_result,
    descriptor: int,
) -> None:
    """Reject replacement or mutation of a strictly opened regular file."""
    final_descriptor = os.fstat(descriptor)
    final_path = lstat_regular_file(path, label=label)
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


def read_strict_regular_file(path: Path, *, label: str) -> bytes:
    """Read a real regular file and reject replacement during the read."""
    descriptor, opened = open_strict_regular_file(path, label=label)
    try:
        chunks: list[bytes] = []
        while block := os.read(descriptor, 1024 * 1024):
            chunks.append(block)
        validate_open_file_unchanged(
            path,
            label=label,
            opened=opened,
            descriptor=descriptor,
        )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def sha256_strict_regular_file(path: Path, *, label: str) -> str:
    """Hash a real regular file and reject replacement during the read."""
    descriptor, opened = open_strict_regular_file(path, label=label)
    digest = hashlib.sha256()
    try:
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
        validate_open_file_unchanged(
            path,
            label=label,
            opened=opened,
            descriptor=descriptor,
        )
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def raise_walk_error(error: OSError) -> None:
    """Make an incomplete filesystem inventory fail explicitly."""
    raise error


def strict_tree_entries(
    directory: Path,
) -> tuple[tuple[Path, Literal["directory", "file"]], ...]:
    """Return a stable inventory containing only real directories and files.

    The root and every descendant are inspected without following symbolic links
    or Windows junctions. Special files are rejected. Each entry's type must also
    agree with the type reported by ``os.walk``; a concurrent replacement that
    changes a file into a directory, or the reverse, therefore fails the
    inventory instead of producing incomplete provenance.

    Traversal errors are propagated and the final tuple is sorted by portable
    root-relative path. Callers can consequently hash the returned tree in a
    deterministic order, but must still use strict per-file reads to detect
    content replacement while bytes are being consumed.
    """
    if is_link_or_junction(directory):
        raise RuntimeError(
            f"Result tree root is a symbolic link or junction: {directory}"
        )
    root_metadata = os.lstat(directory)
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(f"Result tree root is not a real directory: {directory}")

    # ``os.walk`` supplies the candidate names; lstat and redirect detection
    # independently verify each entry before it joins the trusted inventory.
    entries: list[tuple[Path, Literal["directory", "file"]]] = []
    for current, directory_names, filenames in os.walk(
        directory,
        topdown=True,
        onerror=raise_walk_error,
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
            if stat.S_ISLNK(metadata.st_mode) or is_link_or_junction(entry):
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
