# -*- coding: utf-8 -*-
"""
LPM Weibull distribution model.

Purpose
-------
Wrap the SciPy Weibull distribution as an LPM with model metadata.

Author
------
Jean-Raynald de Dreuzy
"""

from scipy.stats import weibull_min

from LPM.core.LPM_scipy import LPMScipy
from LPM.core.registry import register_lpm


@register_lpm("weibull")
class WeibullLpm(LPMScipy):
    """Lumped Parameter Model - Weibull distribution."""

    scipy_dist = weibull_min

    def __init__(self, k=1.0, lambda_=1.0, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        k : float
            Shape parameter (dimensionless).
        lambda_ : float
            Scale parameter (years). Named lambda_ because lambda is reserved.
        directory_lpm : str, optional
            Directory for LPM parameter files.
        """
        parameter_values = {"k": k, "lambda": lambda_}
        parameter_units = {"k": "dimensionless", "lambda": "year"}
        super().__init__("weibull", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        return (self.p["k"],), 0, self.p["lambda"]  # (args), loc, scale
