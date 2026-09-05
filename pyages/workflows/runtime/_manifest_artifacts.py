# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file inventories result artifacts and computes publication tokens.

"""Hash workflow artifacts independently from manifest lifecycle operations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pyages.workflows.runtime._manifest_fs import (
    path_entry_exists as _path_entry_exists,
)
from pyages.workflows.runtime._manifest_fs import (
    sha256_strict_regular_file as _sha256_strict_regular_file,
)
from pyages.workflows.runtime._manifest_fs import (
    strict_tree_entries as _strict_tree_entries,
)

_RUN_STATE_FILENAME = ".pyages-run-state.json"
_TERMINAL_MANIFEST_FILENAME = "result_manifest.json"


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


__all__ = [
    "_publication_token",
    "_RUN_STATE_FILENAME",
    "_snapshot",
    "_TERMINAL_MANIFEST_FILENAME",
]
