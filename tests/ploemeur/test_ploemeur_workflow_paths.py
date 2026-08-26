"""Filesystem contract tests for the Ploemeur workflow."""

from pathlib import Path

from sites.ploemeur.workflows import path_helpers


def test_workflow_temp_folder_creates_missing_directory(
    monkeypatch, tmp_path: Path
) -> None:
    data_directory = tmp_path / "missing" / "data"
    monkeypatch.setattr(
        path_helpers.ploemeur_obs,
        "ploemeur_data_folder",
        lambda: str(data_directory),
    )

    workflow_directory = Path(path_helpers.workflow_temp_folder())

    assert workflow_directory == data_directory / "temp"
    assert workflow_directory.is_dir()
