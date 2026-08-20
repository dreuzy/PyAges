# -*- coding: utf-8 -*-
"""
LPM Weibull distribution model.

Purpose
-------
Wrap the SciPy Weibull distribution as an LPM with model metadata.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np
import numpy.typing as npt
from scipy.special import gamma as gamma_function
from scipy.special import gammainc
from scipy.stats import weibull_min

from pyage.lpm.core.lpm_scipy import LpmScipy
from pyage.lpm.core.registry import register_lpm


@register_lpm("weibull")
class WeibullLpm(LpmScipy):
    """Lumped Parameter Model - Weibull distribution."""

    scipy_dist = weibull_min

    def __init__(self, k=1.0, lambda_=1.0, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        k : float
            Shape parameter (dimensionless).
        lambda_ : float
            Scale parameter (years). Named lambda_ because lambda is reserved.
        directory_lpm : str, optional
            Directory for LPM parameter files.
        """
        parameter_values = {"k": k, "lambda": lambda_}
        parameter_units = {"k": "dimensionless", "lambda": "year"}
        super().__init__("weibull", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (self.p["k"],), 0, self.p["lambda"]  # (args), loc, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return exact cumulative mass and truncated first moment."""
        shape = float(self.p["k"])
        scale = float(self.p["lambda"])
        if not np.isfinite(shape) or shape <= 0.0:
            raise ValueError(f"Weibull shape must be positive and finite, got {shape}")
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"Weibull scale must be positive and finite, got {scale}")

        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        first_moment = np.zeros_like(values, dtype=float)
        positive = values > 0.0
        if np.any(positive):
            with np.errstate(over="ignore", invalid="ignore"):
                reduced_age = np.power(values[positive] / scale, shape)
            moment_shape = 1.0 + 1.0 / shape
            first_moment[positive] = (
                scale
                * gamma_function(moment_shape)
                * gammainc(moment_shape, reduced_age)
            )
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment
