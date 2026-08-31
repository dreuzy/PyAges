# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Output paths owned by the single-date workflow."""

from __future__ import annotations

from pathlib import Path

from pyages.config.paths import (
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    validate_path_component,
)


def dataset_results_directory(
    dataset_name: str,
    *,
    use_default: bool = True,
    directory: str | Path | None = None,
    study_name: str = "test_cases",
) -> Path:
    """Create the configured result directory for one validated dataset."""
    dataset_component = validate_path_component(dataset_name, label="dataset name")
    study_component = validate_path_component(study_name, label="results.study_name")
    if use_default:
        results_root = ROOT_DIRECTORY_RESULTS
    else:
        if directory is None or not str(directory).strip():
            raise ValueError("results.directory must be set when use_default is false.")
        results_root = Path(directory)
    base = result_subdirectory(results_root, study_component)
    return result_subdirectory(base, dataset_component)


__all__ = ["dataset_results_directory"]
