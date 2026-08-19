# -*- coding: utf-8 -*-
"""Helpers for launcher output paths."""

from pyage.config.paths import ROOT_DIRECTORY_RESULTS, result_subdirectory


def dataset_results_directory(dataset_name: str):
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
    str
        Full output path for results/test_cases/<dataset_name>.
    """
    base = result_subdirectory(ROOT_DIRECTORY_RESULTS, "test_cases")
    return result_subdirectory(base, dataset_name)
