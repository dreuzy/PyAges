# -*- coding: utf-8 -*-
"""
LPM Exponential distribution model.
"""

from scipy.stats import expon

from LPM.core.scipy_lpm import ScipyLPM


class LPM_exp(ScipyLPM):
    """Lumped Parameter Model - Exponential distribution."""

    scipy_dist = expon

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
