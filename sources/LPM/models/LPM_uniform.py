# -*- coding: utf-8 -*-
"""
LPM Uniform distribution model.

Purpose
-------
Wrap the SciPy uniform distribution as an LPM with parameter metadata.

Author
------
Jean-Raynald de Dreuzy
"""

from scipy.stats import uniform

from LPM.core.LPM_scipy import LPMScipy
from LPM.core.registry import register_lpm


@register_lpm("uniform")
class LPM_uniform(LPMScipy):
    """Lumped Parameter Model - Uniform distribution."""

    scipy_dist = uniform

    def __init__(self, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'tmin': 2, 'delta': 10}
        parameter_units = {'tmin': 'year', 'delta': 'year'}
        super().__init__("uniform", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        # scipy.stats.uniform(loc, scale) is uniform on [loc, loc+scale]
        return (), self.p['tmin'], self.p['delta']  # (args), loc, scale
