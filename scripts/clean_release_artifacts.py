# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Remove only known, reproducible packaging artifacts from the repository."""

from __future__ import annotations

import shutil
from pathlib import Path

ARTIFACT_DIRECTORIES = (
    "build",
    "dist",
    "pyages.egg-info",
    "pyages.egg-info",
)


def clean_release_artifacts(root: Path | None = None) -> list[Path]:
    """Delete generated build directories below a verified PyAges checkout."""
    repository = (root or Path(__file__).resolve().parents[1]).resolve()
    project_file = repository / "pyproject.toml"
    if (
        not project_file.is_file()
        or 'name = "pyages"' not in project_file.read_text(encoding="utf-8")
    ):
        raise RuntimeError(f"Refusing to clean unverified repository: {repository}")

    removed: list[Path] = []
    for name in ARTIFACT_DIRECTORIES:
        target = (repository / name).resolve()
        if target.parent != repository:
            raise RuntimeError(f"Unsafe artifact target: {target}")
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target)
    return removed


def main() -> None:
    """Clean known artifacts and report the exact removed paths."""
    removed = clean_release_artifacts()
    if not removed:
        print("No release artifacts found.")
        return
    for path in removed:
        print(f"Removed {path}")


if __name__ == "__main__":
    main()
