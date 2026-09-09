# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file builds finite plotting curves for LPMs made of exact age spikes.
# Given a time grid, spike locations, weights, and a display width, it returns
# a normalized interpolation that ordinary PDF tools can sample. Scientific
# convolution still evaluates the original point masses directly.

"""Private numerical approximations used by discrete Dirac LPM models.

This module is used by :mod:`pyages.lpm.models.dirac`,
:mod:`pyages.lpm.models.dirac_double`, and
:mod:`pyages.lpm.models.dirac_double_1_set` to implement their ``pdf()`` methods.
Dirac masses do not have an ordinary probability-density function, so these
helpers build finite-width, linearly interpolated densities solely for generic
PDF sampling and visualization.

This module is not used for convolution. Scientific convolution evaluates the
Dirac masses directly at their exact ages through their dedicated convolution
strategies.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt
from scipy import interpolate


def build_normalized_linear_pdf(
    grid: npt.ArrayLike, density: npt.ArrayLike
) -> Callable[[npt.ArrayLike], npt.NDArray[np.float64]]:
    """Return a zero-extended linear interpolator with unit trapezoidal area.

    Parameters
    ----------
    grid
        One-dimensional, finite, strictly increasing sample coordinates.
    density
        One-dimensional, finite, non-negative density samples with the same
        shape as ``grid``.

    Returns
    -------
    callable
        Linear interpolator. Values outside the sampled grid are zero. If all
        density samples are zero, the returned interpolator is identically
        zero instead of being normalized.

    Raises
    ------
    ValueError
        If the arrays do not satisfy the documented shape, finiteness,
        ordering, or non-negativity requirements.

    Notes
    -----
    Normalization uses the trapezoidal rule because that is the exact integral
    of the piecewise-linear interpolant, including when ``grid`` is nonuniform.
    """
    coordinates = np.asarray(grid, dtype=float)
    samples = np.asarray(density, dtype=float)

    if coordinates.ndim != 1 or coordinates.size < 2:
        raise ValueError("grid must be a one-dimensional array with at least 2 values")
    if samples.ndim != 1 or samples.shape != coordinates.shape:
        raise ValueError("density must be one-dimensional and match grid's shape")
    if not np.all(np.isfinite(coordinates)):
        raise ValueError("grid values must be finite")
    if not np.all(np.diff(coordinates) > 0.0):
        raise ValueError("grid values must be strictly increasing")
    if not np.all(np.isfinite(samples)):
        raise ValueError("density values must be finite")
    if np.any(samples < 0.0):
        raise ValueError("density values must be non-negative")

    area = float(np.trapezoid(samples, coordinates))
    normalized = samples / area if area > 0.0 else samples
    return interpolate.interp1d(
        coordinates,
        normalized,
        kind="linear",
        bounds_error=False,
        fill_value=0.0,
        assume_sorted=True,
    )


def rectangular_dirac_approximation(
    times: npt.ArrayLike, *, center: float = 1.0, width: float = 1.0
) -> npt.NDArray[np.float64]:
    """Sample a finite-width rectangular approximation of a Dirac mass.

    The returned pulse has height ``1 / width`` on the closed interval
    ``[center - width / 2, center + width / 2]`` and is zero elsewhere. Its
    sampled or interpolated integral is normalized separately by
    :func:`build_normalized_linear_pdf`.

    Parameters
    ----------
    times
        Finite coordinates at which to sample the pulse.
    center
        Finite center of the pulse.
    width
        Finite, strictly positive pulse width.

    Returns
    -------
    numpy.ndarray
        Floating-point pulse samples with the same shape as ``times``.

    Raises
    ------
    ValueError
        If a coordinate or scalar parameter is non-finite, or if ``width`` is
        not strictly positive.
    """
    coordinates = np.asarray(times, dtype=float)
    center_value = float(center)
    width_value = float(width)

    if not np.all(np.isfinite(coordinates)):
        raise ValueError("times values must be finite")
    if not np.isfinite(center_value):
        raise ValueError("center must be finite")
    if not np.isfinite(width_value) or width_value <= 0.0:
        raise ValueError("width must be finite and strictly positive")

    half_width = width_value / 2.0
    inside = (coordinates >= center_value - half_width) & (
        coordinates <= center_value + half_width
    )
    return inside.astype(float) / width_value


def build_regularized_dirac_pdf(
    grid: npt.ArrayLike,
    *,
    centers: npt.ArrayLike,
    weights: npt.ArrayLike,
    width: float,
) -> Callable[[npt.ArrayLike], npt.NDArray[np.float64]]:
    """Build a normalized visualization PDF for one or more Dirac masses.

    Parameters
    ----------
    grid
        Coordinates used for the finite-width approximation.
    centers
        Center age of each exact Dirac mass.
    weights
        Finite, non-negative mass associated with each center. The weights do
        not need to sum to one because the sampled result is normalized.
    width
        Common finite width used to visualize every exact mass.

    Returns
    -------
    callable
        Zero-extended, normalized, piecewise-linear PDF approximation.

    Notes
    -----
    This helper is for generic ``pdf()`` sampling and visualization. Exact
    Dirac convolution does not use the returned approximation.
    """
    center_values = np.asarray(centers, dtype=float)
    weight_values = np.asarray(weights, dtype=float)
    if center_values.ndim != 1 or center_values.size == 0:
        raise ValueError("centers must be a non-empty one-dimensional array")
    if weight_values.ndim != 1 or weight_values.shape != center_values.shape:
        raise ValueError("weights must be one-dimensional and match centers")
    if not np.all(np.isfinite(center_values)):
        raise ValueError("centers must be finite")
    if not np.all(np.isfinite(weight_values)) or np.any(weight_values < 0.0):
        raise ValueError("weights must be finite and non-negative")
    if float(weight_values.sum()) <= 0.0:
        raise ValueError("weights must contain positive total mass")

    coordinates = np.asarray(grid, dtype=float)
    density = np.zeros_like(coordinates, dtype=float)
    for center, weight in zip(center_values, weight_values, strict=True):
        density += weight * rectangular_dirac_approximation(
            coordinates,
            center=float(center),
            width=width,
        )
    return build_normalized_linear_pdf(coordinates, density)
