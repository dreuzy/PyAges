# -*- coding: utf-8 -*-
"""
LPM Shifted Inverse Gaussian distribution model.

Purpose
-------
Wrap the SciPy inverse Gaussian distribution with an added shift parameter,
providing an LPM-compatible shifted inverse-Gaussian PDF.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np
import numpy.typing as npt
from scipy.stats import invgauss

from pyage.lpm.core.lpm_scipy import LpmScipySafe
from pyage.lpm.core.registry import register_lpm
from pyage.lpm.models.inverse_gaussian import (
    cdf_and_partial_first_moment_from_mean_std,
    scipy_params_from_mean_std,
)


@register_lpm("ig_shifted")
class InverseGaussianShiftedLpm(LpmScipySafe):
    """Lumped Parameter Model - Shifted Inverse Gaussian distribution."""

    scipy_dist = invgauss

    def __init__(self, mu=10, sigma=2, shift=5, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean of the dispersive component in years, excluding ``shift``.
        sigma : float
            Standard deviation of the dispersive component in years.
        shift : float
            Location shift (loc parameter).
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'mu': mu, 'sigma': sigma, 'shift': shift}
        parameter_units = {'mu': 'year', 'sigma': 'year', 'shift': 'year'}
        super().__init__("ig_shifted", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        shape, scale = scipy_params_from_mean_std(self.p['mu'], self.p['sigma'])
        return (shape,), self.p['shift'], scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return the CDF and raw truncated first moment after shifting."""
        values = np.asarray(t, dtype=float)
        cdf, component_moment = cdf_and_partial_first_moment_from_mean_std(
            values - self.p['shift'],
            self.p['mu'],
            self.p['sigma'],
        )
        cdf = np.asarray(cdf, dtype=float)
        raw_moment = self.p['shift'] * cdf + np.asarray(
            component_moment,
            dtype=float,
        )
        if values.ndim == 0:
            return float(cdf), float(raw_moment)
        return cdf, raw_moment
