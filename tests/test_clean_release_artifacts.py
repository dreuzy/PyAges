# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Safety tests for release-artifact cleanup."""

from pathlib import Path

import pytest

from scripts.maintenance.clean_release_artifacts import clean_release_artifacts


def test_clean_release_artifacts_removes_only_known_directories(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pyages"\n',
        encoding="utf-8",
    )
    artifact = tmp_path / "dist"
    artifact.mkdir()
    (artifact / "old.whl").write_text("generated", encoding="utf-8")
    preserved = tmp_path / "results"
    preserved.mkdir()

    removed = clean_release_artifacts(tmp_path)

    assert removed == [artifact]
    assert not artifact.exists()
    assert preserved.is_dir()


def test_clean_release_artifacts_optionally_removes_caches(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pyages"\n',
        encoding="utf-8",
    )
    cache = tmp_path / ".pytest_cache"
    cache.mkdir()
    generated_docs = tmp_path / "docs" / "_build"
    generated_docs.mkdir(parents=True)
    nested_cache = tmp_path / "pyages" / "module" / "__pycache__"
    nested_cache.mkdir(parents=True)
    dotnet_build = (
        tmp_path / "validation" / "tracerlpm" / "src" / "TracerLpmRunner" / "bin"
    )
    dotnet_build.mkdir(parents=True)
    coverage = tmp_path / ".coverage"
    coverage.write_text("generated", encoding="utf-8")
    preserved = tmp_path / "results"
    preserved.mkdir()

    removed = clean_release_artifacts(tmp_path, include_caches=True)

    assert removed == [cache, generated_docs, dotnet_build, coverage, nested_cache]
    assert not cache.exists()
    assert not generated_docs.exists()
    assert not nested_cache.exists()
    assert not dotnet_build.exists()
    assert not coverage.exists()
    assert preserved.is_dir()


def test_clean_release_artifacts_refuses_unverified_directory(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()

    with pytest.raises(RuntimeError, match="unverified repository"):
        clean_release_artifacts(tmp_path)

    assert (tmp_path / "dist").is_dir()
