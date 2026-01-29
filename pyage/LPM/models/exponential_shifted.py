# -*- coding: utf-8 -*-
"""
LPM Shifted Exponential distribution model.

Purpose
-------
Wrap the SciPy exponential distribution with an added shift parameter,
providing an LPM-compatible shifted exponential PDF.

Author
------
Jean-Raynald de Dreuzy
"""

from scipy.stats import expon

from LPM.core.lpm_scipy import LpmScipy
from LPM.core.convolution_strategy import ConvolutionStrategy
from LPM.core.registry import register_lpm


@register_lpm("exp_shifted")
class ExponentialShiftedLpm(LpmScipy):
    """Lumped Parameter Model - Shifted Exponential distribution."""

    scipy_dist = expon
    convolution_strategy = ConvolutionStrategy.EXPONENTIAL

    def __init__(self, mu=10, shift=10, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean of the exponential distribution (scale parameter).
        shift : float
            Location shift (loc parameter).
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'mu': mu, 'shift': shift}
        parameter_units = {'mu': 'year', 'shift': 'year'}
        super().__init__("exp_shifted", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (), self.p['shift'], self.p['mu']  # (args), loc, scale
