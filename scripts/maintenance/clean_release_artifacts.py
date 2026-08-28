# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Remove only known, reproducible artifacts from the repository."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ARTIFACT_DIRECTORIES = (
    "build",
    "dist",
    "pyages.egg-info",
)
CACHE_DIRECTORIES = (
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "docs/_build",
    "docs/api/generated",
    "validation/tracerlpm/src/TracerLpmRunner/bin",
    "validation/tracerlpm/src/TracerLpmRunner/obj",
)
CACHE_FILES = (
    ".coverage",
    "coverage.xml",
)
PYTHON_CACHE_ROOTS = (
    "article",
    "data_core",
    "examples",
    "pyages",
    "scripts",
    "sites",
    "tests",
    "validation",
)


def _artifact_candidates(repository: Path, *, include_caches: bool) -> list[Path]:
    """Return explicit and recursively discovered cleanup candidates."""
    names = list(ARTIFACT_DIRECTORIES)
    if not include_caches:
        return [repository / name for name in names]

    names.extend(CACHE_DIRECTORIES)
    names.extend(CACHE_FILES)
    candidates = [repository / name for name in names]
    for root_name in PYTHON_CACHE_ROOTS:
        cache_root = repository / root_name
        if cache_root.is_dir():
            candidates.extend(cache_root.rglob("__pycache__"))
    return candidates


def _safe_artifact_target(repository: Path, candidate: Path) -> Path:
    """Resolve one cleanup target while rejecting unsafe paths and symlinks."""
    if candidate.is_symlink():
        raise RuntimeError(f"Refusing to clean symlinked artifact: {candidate}")
    target = candidate.resolve()
    if target == repository or repository not in target.parents:
        raise RuntimeError(f"Unsafe artifact target: {target}")
    return target


def clean_release_artifacts(
    root: Path | None = None,
    *,
    include_caches: bool = False,
) -> list[Path]:
    """Delete selected generated artifacts below a verified PyAges checkout."""
    repository = (root or Path(__file__).resolve().parents[2]).resolve()
    project_file = repository / "pyproject.toml"
    if not project_file.is_file() or 'name = "pyages"' not in project_file.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError(f"Refusing to clean unverified repository: {repository}")

    removed: list[Path] = []
    seen: set[Path] = set()
    for candidate in _artifact_candidates(repository, include_caches=include_caches):
        target = _safe_artifact_target(repository, candidate)
        if target in seen:
            continue
        seen.add(target)
        if target.is_dir():
            shutil.rmtree(target)
            removed.append(target)
        elif target.is_file():
            target.unlink()
            removed.append(target)
    return removed


def main() -> None:
    """Clean known artifacts and report the exact removed paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-caches",
        action="store_true",
        help=(
            "also remove project Python caches, coverage files, generated docs, "
            "and TracerLPM build outputs"
        ),
    )
    args = parser.parse_args()
    removed = clean_release_artifacts(include_caches=args.include_caches)
    if not removed:
        print("No release artifacts found.")
        return
    for path in removed:
        print(f"Removed {path}")


if __name__ == "__main__":
    main()
