# -*- coding: utf-8 -*-
"""
LPM Exponential distribution model.

Purpose
-------
Wrap the SciPy exponential distribution as an LPM with model metadata.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np
import numpy.typing as npt
from scipy.special import gammainc
from scipy.stats import expon

from pyage.lpm.core.lpm_scipy import LpmScipy
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.core.registry import register_lpm


def cdf_and_partial_first_moment_from_scale_shift(
    t: npt.ArrayLike,
    scale: float,
    shift: float = 0.0,
) -> tuple[npt.ArrayLike, npt.ArrayLike]:
    """Return the CDF and raw truncated first moment of ``shift + Exp(scale)``."""
    scale = float(scale)
    shift = float(shift)
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError(f"Exponential scale must be positive and finite, got {scale}")
    if not np.isfinite(shift):
        raise ValueError(f"Exponential shift must be finite, got {shift}")

    values = np.asarray(t, dtype=float)
    cdf = np.zeros_like(values, dtype=float)
    first_moment = np.zeros_like(values, dtype=float)
    supported = values > shift
    if np.any(supported):
        z = (values[supported] - shift) / scale
        component_cdf = -np.expm1(-z)
        component_moment = scale * gammainc(2.0, z)
        cdf[supported] = component_cdf
        first_moment[supported] = shift * component_cdf + component_moment

    if values.ndim == 0:
        return float(cdf), float(first_moment)
    return cdf, first_moment


@register_lpm("exp")
class ExponentialLpm(LpmScipy):
    """Lumped Parameter Model - Exponential distribution."""

    scipy_dist = expon
    convolution_strategy = ConvolutionStrategy.CONTINUOUS

    def __init__(self, mu=10, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean of the exponential distribution (scale parameter).
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'mu': mu}
        parameter_units = {'mu': 'year'}
        super().__init__("exp", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (), 0, self.p['mu']  # (args), loc, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return exact cumulative mass and truncated first moment."""
        return cdf_and_partial_first_moment_from_scale_shift(t, self.p['mu'])
