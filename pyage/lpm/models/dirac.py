# -*- coding: utf-8 -*-
"""
LPM Dirac (delta) distribution model.

Purpose
-------
Define a single-spike (Dirac) lumped-parameter model, providing a discretized
PDF for convolution workflows.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np

from pyage.lpm.core.lpm_base import LpmBase
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.core.registry import register_lpm
import pyage.lpm.core.tools_interpolation as tools_interpolation


@register_lpm("dirac")
class DiracLpm(LpmBase):
    """Lumped Parameter Model representing a single Dirac spike."""

    convolution_strategy = ConvolutionStrategy.DIRAC

    def __init__(self, mu=10, directory_lpm=None):
        """
        Initialize a Dirac LPM.

        Parameters
        ----------
        mu : float, optional
            Dirac spike location (years).
        directory_lpm : str or None
            Directory containing LPM parameter files.
        """
        parameter_values = {"mu": mu}
        parameter_units = {"mu": "year"}
        LpmBase.__init__(self, "dirac", parameter_values, parameter_units, directory_lpm)
                
    
    def get_dirac_time(self):
        """Return the Dirac spike time."""
        return self.p["mu"]
        
    
    def set_interp(self):
        """
        Build the interpolated, normalized PDF for the Dirac spike.
        """
        # Width of the Dirac 
        width = max(1, self.get_param_range("mu") / 200)
        # A somewhat larger time range than the bounds of the Dirac
        td = 1.2 * self.get_p_max("mu") * np.arange(0, 201) / 200
        # Values of the function on the time discretization
        pdfd = tools_interpolation.dirac_discret(td, center=self.p["mu"], width=width)
        self.f = tools_interpolation.interp_normalize(td, pdfd)


    def pdf(self, t):
        """Return the probability density function at time ``t``."""
        self.set_interp()
        return self.f(t)
    
    
    def cdf(self, t):
        """Return the cumulative distribution function at time ``t``."""
        values = np.asarray(t, dtype=float)
        result = (values >= self.p["mu"]).astype(float)
        return float(result) if values.ndim == 0 else result
    

    def cdf_inv(self, p):
        """Return the inverse CDF (quantile) for probability ``p``."""
        return self.p["mu"]
    
    
    def mean(self):
        """Return the mean of the distribution."""
        return self.p["mu"]
    
    
    def std(self):
        """Return the standard deviation of the distribution."""
        return 0.0
   
