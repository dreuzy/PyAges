# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file converts inverse-Gaussian parameters between two naming systems.

"""Convert shifted inverse-Gaussian parameters between PyAges and SciPy.

PyAges describes the distribution with its physical mean ``M``, standard
deviation ``S``, and time shift ``t0``. Earlier Ploemeur experiments described
the same distribution with SciPy's ``shape``, ``scale``, and ``shift`` values.

This module contains both conversion directions and the associated Jacobian.
Keeping the formulas together makes it possible to check how a proposal or
probability density changes when it moves between the two parameter systems.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def physical_moments_to_scipy(mean: float, std: float) -> tuple[float, float]:
    """Return SciPy ``(shape, scale)`` for physical moments ``(M, S)``."""
    mean = float(mean)
    std = float(std)
    if not math.isfinite(mean) or not math.isfinite(std) or mean <= 0.0 or std <= 0.0:
        return math.nan, math.nan
    return std**2 / mean**2, mean**3 / std**2


def scipy_to_physical_moments(shape: float, scale: float) -> tuple[float, float]:
    """Return physical moments ``(M, S)`` for SciPy ``(shape, scale)``."""
    shape = float(shape)
    scale = float(scale)
    if (
        not math.isfinite(shape)
        or not math.isfinite(scale)
        or shape <= 0.0
        or scale <= 0.0
    ):
        return math.nan, math.nan
    return shape * scale, scale * shape**1.5


def scipy_to_physical_abs_det_jacobian(shape: float, scale: float) -> float:
    """Return ``|d(M,S)/d(shape,scale)| = S/2`` for the IG mapping."""
    _, std = scipy_to_physical_moments(shape, scale)
    return std / 2.0


def physical_to_scipy_coordinates(theta: Sequence[float]) -> np.ndarray:
    """Return ``(shape, scale, shift)`` from physical ``(M, S, t0)``."""
    values = np.asarray(theta, dtype=float)
    if values.shape != (3,):
        raise ValueError("physical IG coordinates require exactly three parameters")
    shape, scale = physical_moments_to_scipy(values[0], values[1])
    return np.array([shape, scale, values[2]], dtype=float)


def scipy_to_physical_coordinates(theta: Sequence[float]) -> np.ndarray:
    """Return physical ``(M, S, t0)`` from ``(shape, scale, shift)``."""
    values = np.asarray(theta, dtype=float)
    if values.shape != (3,):
        raise ValueError("SciPy IG coordinates require exactly three parameters")
    mean, std = scipy_to_physical_moments(values[0], values[1])
    return np.array([mean, std, values[2]], dtype=float)


__all__ = [
    "physical_moments_to_scipy",
    "physical_to_scipy_coordinates",
    "scipy_to_physical_abs_det_jacobian",
    "scipy_to_physical_coordinates",
    "scipy_to_physical_moments",
]
