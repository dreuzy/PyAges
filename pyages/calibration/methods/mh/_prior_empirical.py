# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file converts empirical histogram points into a usable MH prior density.

"""Build a bounded numerical prior from sampled density values.

Input coordinates must be finite, strictly increasing, and paired with finite
non-negative densities. Linear interpolation fills the observed portion of the
requested grid, optional exponential tails extend beyond the supplied points,
and numerical integration normalizes the result to unit mass.

The same grid representation can be integrated to obtain its mean and variance
for chain initialization and validation. This module prepares a density; it does
not draw samples or evaluate an MH acceptance probability.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy.interpolate import interp1d

EMPIRICAL_GRID_POINTS = 101
EMPIRICAL_RELATIVE_TAIL_DECAY = 500.0


def _validated_empirical_inputs(
    x_data: Sequence[float],
    y_data: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(x_data, dtype=float)
    density = np.asarray(y_data, dtype=float)
    if values.ndim != 1 or density.ndim != 1 or values.shape != density.shape:
        raise ValueError(
            "x_data and y_data must be one-dimensional arrays of equal size"
        )
    if values.size < 2:
        raise ValueError("An empirical prior requires at least two grid points")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(density)):
        raise ValueError("Empirical prior values and densities must be finite")
    if np.any(np.diff(values) <= 0.0):
        raise ValueError("Empirical prior values must be strictly increasing")
    if np.any(density < 0.0):
        raise ValueError("Empirical prior densities must be non-negative")
    return values, density


def _validate_grid_controls(
    xmin: float,
    xmax: float,
    n_points: int,
    decay_left: float,
    decay_right: float,
) -> None:
    if not math.isfinite(xmin) or not math.isfinite(xmax) or xmax <= xmin:
        raise ValueError("Empirical prior bounds must be finite and increasing")
    if isinstance(n_points, bool) or not isinstance(n_points, int) or n_points < 2:
        raise ValueError("n_points must be an integer greater than one")
    if (
        not math.isfinite(decay_left)
        or not math.isfinite(decay_right)
        or decay_left < 0.0
        or decay_right < 0.0
    ):
        raise ValueError("Empirical prior decay rates must be finite and non-negative")


def build_empirical_prior_grid(
    x_data: Sequence[float],
    y_data: Sequence[float],
    xmin: float = 0.0,
    xmax: float = 70.0,
    n_points: int = 2000,
    decay_left: float = 10.0,
    decay_right: float = 10.0,
    normalize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate histogram points over one bounded, normalized density grid."""
    x_data, y_data = _validated_empirical_inputs(x_data, y_data)
    _validate_grid_controls(xmin, xmax, n_points, decay_left, decay_right)
    interpolate = interp1d(
        x_data,
        y_data,
        kind="linear",
        bounds_error=False,
        fill_value=0,
    )
    x_cont = np.linspace(xmin, xmax, n_points)
    y_cont = interpolate(x_cont)
    left_mask = x_cont < x_data.min()
    right_mask = x_cont > x_data.max()
    if y_data[0] > 0:
        y_cont[left_mask] = y_data[0] * np.exp(
            -decay_left * (x_data[0] - x_cont[left_mask])
        )
    if y_data[-1] > 0:
        y_cont[right_mask] = y_data[-1] * np.exp(
            -decay_right * (x_cont[right_mask] - x_data[-1])
        )
    if normalize:
        area = np.trapezoid(y_cont, x_cont)
        if not math.isfinite(area) or area <= 0.0:
            raise ValueError("Empirical prior must have positive finite mass")
        y_cont /= area
    return x_cont, y_cont


def histogram_moments(histogram: np.ndarray) -> tuple[float, float]:
    """Integrate mean and variance from a two-column density grid."""
    density = histogram[:, 1]
    values = histogram[:, 0]
    total = float(np.trapezoid(density, values))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("Histogram density must have positive finite mass")
    mean = float(np.trapezoid(values * density, values) / total)
    second = float(np.trapezoid(values**2 * density, values) / total)
    return mean, max(0.0, second - mean**2)


__all__ = [
    "EMPIRICAL_GRID_POINTS",
    "EMPIRICAL_RELATIVE_TAIL_DECAY",
    "build_empirical_prior_grid",
    "histogram_moments",
]
