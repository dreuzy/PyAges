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

import LPM.core.LPM_root as LPM
import LPM.core.tools_interpolation as tools_interpolation


class LPM_dirac(LPM.LPM):
    """
    Lumped Parameter Model - Dirac distribution.

    Methods
    -------
    get_dirac_time()
        Return the Dirac spike time (mu).
    """

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
        LPM.LPM.__init__(self, "dirac", parameter_values, parameter_units, directory_lpm)
                
    
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
        return (t > self.p["mu"]).astype(int)
    

    def cdf_inv(self, p):
        """Return the inverse CDF (quantile) for probability ``p``."""
        return self.p["mu"]
    
    
    def mean(self):
        """Return the mean of the distribution."""
        return self.p["mu"]
    
    
    def std(self):
        """Return the standard deviation of the distribution."""
        return 0.0
   
