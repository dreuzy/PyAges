# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file publishes complete CLI-generated text files without exposing a
# partially written destination or overwriting a concurrently created file.

"""Publish complete text files with explicit overwrite semantics."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _staged_text_file(
    destination: Path,
    content: str,
    *,
    encoding: str,
) -> Path:
    """Write, flush, and close one private sibling of *destination*."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # fdopen owns the descriptor after construction; closing it again may
        # fail harmlessly if the context manager already handled the error.
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def atomic_write_text(
    destination: str | Path,
    content: str,
    *,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Publish complete *content* while honoring one overwrite policy.

    A private file is written in the destination directory so publication
    stays on one filesystem. Create-only publication uses a hard link: the
    filesystem creates the destination name only if that name is still absent.
    Replacement uses :func:`os.replace`, which exposes either the old complete
    file or the new complete file.
    """
    path = Path(destination)
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Destination directory does not exist: {path.parent}")

    temporary = _staged_text_file(path, content, encoding=encoding)
    try:
        if overwrite:
            os.replace(temporary, path)
        else:
            # Linking a fully written sibling is an atomic no-clobber publish:
            # FileExistsError wins over any earlier, now-stale exists() check.
            os.link(temporary, path)
            try:
                temporary.unlink()
            except OSError:
                # Publication already succeeded. A hidden staging file is less
                # harmful than reporting failure for a valid destination.
                pass
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return path


__all__ = ["atomic_write_text"]
