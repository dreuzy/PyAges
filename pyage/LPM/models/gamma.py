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

from scipy.stats import gamma

from pyage.LPM.core.lpm_scipy import LpmScipy
from pyage.LPM.core.registry import register_lpm


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
