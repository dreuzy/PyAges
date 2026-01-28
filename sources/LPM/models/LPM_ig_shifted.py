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

from scipy.stats import invgauss

from LPM.core.LPM_scipy import LPMScipySafe


class LPM_ig_shifted(LPMScipySafe):
    """Lumped Parameter Model - Shifted Inverse Gaussian distribution."""

    scipy_dist = invgauss

    def __init__(self, mu=10, sigma=2, shift=5, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean parameter of the inverse Gaussian distribution.
        sigma : float
            Scale parameter of the inverse Gaussian distribution.
        shift : float
            Location shift (loc parameter).
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'mu': mu, 'sigma': sigma, 'shift': shift}
        parameter_units = {'mu': 'year', 'sigma': 'year', 'shift': 'year'}
        super().__init__("ig_shifted", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (self.p['mu'],), self.p['shift'], self.p['sigma']  # (args), loc, scale
