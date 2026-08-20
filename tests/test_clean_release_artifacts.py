"""Safety tests for release-artifact cleanup."""

from pathlib import Path

import pytest

from scripts.clean_release_artifacts import clean_release_artifacts


def test_clean_release_artifacts_removes_only_known_directories(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pyage-groundwater"\n',
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


def test_clean_release_artifacts_refuses_unverified_directory(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()

    with pytest.raises(RuntimeError, match="unverified repository"):
        clean_release_artifacts(tmp_path)

    assert (tmp_path / "dist").is_dir()
