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


def dataset_results_directory(dataset_name: str) -> Path:
    """Create the result directory for one validated dataset filename."""
    component = validate_path_component(dataset_name, label="dataset name")
    base = result_subdirectory(ROOT_DIRECTORY_RESULTS, "test_cases")
    return result_subdirectory(base, component)


__all__ = ["dataset_results_directory"]
