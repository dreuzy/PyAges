# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
LPM Uniform distribution model.

Purpose
-------
Wrap the SciPy uniform distribution as an LPM with parameter metadata.

"""

import numpy as np
import numpy.typing as npt
from scipy.stats import uniform

from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.core.registry import register_lpm


@register_lpm("uniform")
class UniformLpm(LpmScipy):
    """Lumped Parameter Model - Uniform distribution."""

    scipy_dist = uniform

    def __init__(self, tmin=2, delta=10, directory_lpm=None):
        """
        Initialize a uniform transit-time distribution.

        Parameters
        ----------
        tmin : float
            Lower support bound in years.
        delta : float
            Strictly positive support width in years.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {"tmin": tmin, "delta": delta}
        parameter_units = {"tmin": "year", "delta": "year"}
        super().__init__("uniform", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        # scipy.stats.uniform(loc, scale) is uniform on [loc, loc+scale]
        return (), self.p["tmin"], self.p["delta"]  # (args), loc, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return exact cumulative mass and truncated first moment."""
        lower = float(self.p["tmin"])
        width = float(self.p["delta"])
        if not np.isfinite(lower):
            raise ValueError(f"Uniform lower bound must be finite, got {lower}")
        if not np.isfinite(width) or width <= 0.0:
            raise ValueError(f"Uniform width must be positive and finite, got {width}")

        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        clipped = np.clip(values, lower, lower + width)
        first_moment = np.where(
            values > lower,
            (clipped - lower) * (clipped + lower) / (2.0 * width),
            0.0,
        )
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment
