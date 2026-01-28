# -*- coding: utf-8 -*-
"""
LPM Inverse Gaussian distribution model.

Purpose
-------
Wrap the SciPy inverse Gaussian distribution as an LPM with metadata.

Reference
---------
Waugh, D., and T. Hall (2002), Age of stratospheric air: Theory, observations,
and models, Reviews of Geophysics, 40(4), 1-1-1-26,
doi:https://doi.org/10.1029/2000RG000101.

Author
------
Jean-Raynald de Dreuzy
"""

from scipy.stats import invgauss

from LPM.core.LPM_scipy import LPMScipySafe


class LPM_ig(LPMScipySafe):
    """Lumped Parameter Model - Inverse Gaussian distribution."""

    scipy_dist = invgauss

    def __init__(self, mu=10, sigma=2, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean parameter of the inverse Gaussian distribution.
        sigma : float
            Scale parameter of the inverse Gaussian distribution.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'mu': mu, 'sigma': sigma}
        parameter_units = {'mu': 'year', 'sigma': 'year'}
        super().__init__("ig", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (self.p['mu'],), 0, self.p['sigma']  # (args), loc, scale
