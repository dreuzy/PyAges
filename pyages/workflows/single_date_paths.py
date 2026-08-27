# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Output-path helpers for the installable single-date workflow."""

from __future__ import annotations

from pathlib import Path

from pyages.config.paths import ROOT_DIRECTORY_RESULTS, result_subdirectory


def configuration_root(config_path: str | Path) -> Path:
    """Resolve checkout-relative configs while supporting standalone projects."""
    path = Path(config_path).resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "data_core"
        ).is_dir():
            return candidate
    current_directory = Path.cwd().resolve()
    if (current_directory / "pyproject.toml").is_file() and (
        current_directory / "data_core"
    ).is_dir():
        return current_directory
    return path.parent


def dataset_results_directory(dataset_name: str) -> Path:
    """
    Purpose
    -------
    Build the base results directory for a dataset.

    Parameters
    ----------
    dataset_name : str
        Dataset identifier used to name the output folder.

    Returns
    -------
    Path
        Full output path for results/test_cases/<dataset_name>.
    """
    base = result_subdirectory(ROOT_DIRECTORY_RESULTS, "test_cases")
    return result_subdirectory(base, dataset_name)


__all__ = ["configuration_root", "dataset_results_directory"]
