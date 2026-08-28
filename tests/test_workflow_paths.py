# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Path-resolution tests shared by installable workflows."""

from pathlib import Path

import pytest

from pyages.config.paths import configuration_root
from pyages.workflows.single_date.paths import dataset_results_directory


def test_configuration_root_finds_checkout_from_nested_config(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "data_core").mkdir()
    config = tmp_path / "examples" / "case" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("dataset: {}\n", encoding="utf-8")

    assert configuration_root(config) == tmp_path


def test_configuration_root_falls_back_to_config_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "standalone" / "config.yaml"
    config.parent.mkdir()
    config.write_text("dataset: {}\n", encoding="utf-8")

    assert configuration_root(config) == config.parent


def test_configuration_root_accepts_checkout_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (checkout / "data_core").mkdir()
    config = tmp_path / "copied" / "config.yaml"
    config.parent.mkdir()
    config.write_text("dataset: {}\n", encoding="utf-8")
    monkeypatch.chdir(checkout)

    assert configuration_root(config) == checkout


@pytest.mark.parametrize(
    "dataset_name",
    ["../escape.txt", "..\\escape.txt", "D:escape.txt", ".", ".."],
)
def test_dataset_results_directory_rejects_path_components(dataset_name: str) -> None:
    with pytest.raises(ValueError, match="single non-empty path component"):
        dataset_results_directory(dataset_name)
