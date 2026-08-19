# -*- coding: utf-8 -*-
"""
LPM Gamma distribution model.

Purpose
-------
Wrap the SciPy gamma distribution as an LPM with parameter metadata.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np
import numpy.typing as npt
from scipy.special import gammainc
from scipy.stats import gamma

from pyage.lpm.core.lpm_scipy import LpmScipy
from pyage.lpm.core.registry import register_lpm


@register_lpm("gamma")
class GammaLpm(LpmScipy):
    """Lumped Parameter Model - Gamma distribution."""

    scipy_dist = gamma

    def __init__(self, k=2, scale=10, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        k : float
            Shape parameter of the gamma distribution.
        scale : float
            Scale parameter of the gamma distribution.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'k': k, 'scale': scale}
        parameter_units = {'k': '', 'scale': 'year'}
        super().__init__("gamma", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (self.p['k'],), 0, self.p['scale']  # (args), loc, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return exact cumulative mass and truncated first moment."""
        shape = float(self.p['k'])
        scale = float(self.p['scale'])
        if not np.isfinite(shape) or shape <= 0.0:
            raise ValueError(f"Gamma shape must be positive and finite, got {shape}")
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"Gamma scale must be positive and finite, got {scale}")

        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        first_moment = np.zeros_like(values, dtype=float)
        positive = values > 0.0
        if np.any(positive):
            first_moment[positive] = (
                shape
                * scale
                * gammainc(shape + 1.0, values[positive] / scale)
            )
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment
