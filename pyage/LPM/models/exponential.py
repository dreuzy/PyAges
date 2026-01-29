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

from scipy.stats import expon

from LPM.core.LPM_scipy import LPMScipy
from LPM.core.convolution_strategy import ConvolutionStrategy
from LPM.core.registry import register_lpm


@register_lpm("exp")
class ExponentialLpm(LPMScipy):
    """Lumped Parameter Model - Exponential distribution."""

    scipy_dist = expon
    convolution_strategy = ConvolutionStrategy.EXPONENTIAL

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
