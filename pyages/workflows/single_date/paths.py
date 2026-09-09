# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file builds the public result path for one single-date dataset from the
# dataset name, study name, and either the default or configured results root.
# It validates user-controlled path components before returning the nested
# directory, preventing them from escaping the selected root.

"""Output paths owned by the single-date workflow."""

from __future__ import annotations

from pathlib import Path

from pyages.config.paths import (
    ROOT_DIRECTORY_RESULTS,
    validate_path_component,
)


def dataset_results_directory(
    dataset_name: str,
    *,
    use_default: bool = True,
    directory: str | Path | None = None,
    study_name: str = "test_cases",
    create: bool = True,
) -> Path:
    """Return the configured result directory for one validated dataset.

    Set ``create=False`` when the caller will hand the path to the staged-result
    lifecycle, which must keep a new public leaf absent until promotion.
    """
    dataset_component = validate_path_component(dataset_name, label="dataset name")
    study_component = validate_path_component(study_name, label="results.study_name")
    if use_default:
        results_root = ROOT_DIRECTORY_RESULTS
    else:
        if directory is None or not str(directory).strip():
            raise ValueError("results.directory must be set when use_default is false.")
        results_root = Path(directory)
    path = Path(results_root) / study_component / dataset_component
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["dataset_results_directory"]
