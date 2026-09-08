# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Path-resolution tests shared by installable workflows."""

from pathlib import Path

import pytest

import pyages.workflows.single_date.paths as single_date_paths
from pyages.config.paths import configuration_directory
from pyages.workflows.single_date.paths import dataset_results_directory


def test_configuration_directory_is_always_the_yaml_parent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "data_core").mkdir()
    config = tmp_path / "examples" / "generated" / "pyages.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "schema_version: 3\nworkflow:\n  kind: single_date\n",
        encoding="utf-8",
    )

    assert configuration_directory(config) == config.parent


@pytest.mark.parametrize(
    "dataset_name",
    ["../escape.txt", "..\\escape.txt", "D:escape.txt", ".", ".."],
)
def test_dataset_results_directory_rejects_path_components(dataset_name: str) -> None:
    with pytest.raises(ValueError, match="single non-empty path component"):
        dataset_results_directory(dataset_name)


def test_dataset_results_directory_uses_the_default_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    results_root = tmp_path / "default-results"
    monkeypatch.setattr(single_date_paths, "ROOT_DIRECTORY_RESULTS", results_root)

    output = dataset_results_directory("observations.txt")

    assert output == results_root / "test_cases" / "observations.txt"
    assert output.is_dir()


def test_dataset_results_directory_isolates_studies_for_the_same_dataset(
    tmp_path: Path,
) -> None:
    first = dataset_results_directory(
        "observations.txt",
        use_default=False,
        directory=tmp_path,
        study_name="profile_a",
    )
    second = dataset_results_directory(
        "observations.txt",
        use_default=False,
        directory=tmp_path,
        study_name="profile_b",
    )

    assert first == tmp_path / "profile_a" / "observations.txt"
    assert second == tmp_path / "profile_b" / "observations.txt"
    assert first != second


def test_dataset_results_directory_can_leave_the_public_leaf_absent(
    tmp_path: Path,
) -> None:
    output = dataset_results_directory(
        "observations.txt",
        use_default=False,
        directory=tmp_path,
        study_name="staged",
        create=False,
    )

    assert output == tmp_path / "staged" / "observations.txt"
    assert not output.exists()
