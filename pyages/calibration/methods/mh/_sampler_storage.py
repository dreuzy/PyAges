# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file allocates the retained-sample table and builds each row from model
# parameters, fit quality, predicted concentrations, and the bounds flag.

"""Allocate and compose retained rows for one MH chain."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from pyages.calibration.objective import normalized_residual_norm


def prepare_retained_storage(
    lpm: Any,
    observation_keys: Sequence[str],
    row_count: int,
) -> tuple[np.ndarray, list[str]]:
    """Return a zeroed retained matrix and its canonical column names."""
    column_names = (
        lpm.get_param_names()
        + ["obj_function"]
        + list(observation_keys)
        + ["param_in_bounds"]
    )
    return np.zeros((row_count, len(column_names)), dtype=float), column_names


def retained_row(
    params: list[float],
    chi_square: float,
    concentrations: list[float],
) -> list[float]:
    """Compose one retained current-state row in the persisted schema."""
    return (
        params
        + [normalized_residual_norm(chi_square, len(concentrations))]
        + concentrations
        + [1.0]
    )


__all__ = ["prepare_retained_storage", "retained_row"]
