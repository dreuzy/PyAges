# -*- coding: utf-8 -*-
"""
LPM Double-Dirac (one fixed spike) distribution model.

Purpose
-------
Define a two-spike (Dirac) LPM where one spike is fixed (muset) and the
other is free (mufree), producing a discretized PDF for convolution.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np

from LPM.core.lpm_base import LpmBase
from LPM.core.convolution_strategy import ConvolutionStrategy
from LPM.core.registry import register_lpm
import LPM.core.tools_interpolation as tools_interpolation


@register_lpm("dirac_double_1_set")
class DiracDouble1SetLpm(LpmBase):
    """
    Lumped Parameter Model - Double Dirac with one fixed spike.
    """

    convolution_strategy = ConvolutionStrategy.DIRAC_DOUBLE

    def __init__(self, mufree=10, muset=70, rate=0.2, directory_lpm=None):
        """
        Initialize a double-Dirac LPM with one fixed spike.

        Parameters
        ----------
        mufree : float
            Location of the free spike (years).
        muset : float
            Location of the fixed spike (years).
        rate : float
            Mixing weight for the free spike.
        directory_lpm : str or None
            Directory containing LPM parameter files.
        """
        self.__muset = muset
        parameter_values = {"mufree": mufree, "rate": rate}
        parameter_units = {"mufree": "year", "rate": ""}
        LpmBase.__init__(self, "dirac_double_1_set", parameter_values, parameter_units, directory_lpm)
                
    
    def get_dirac_double_time(self):
        """Return the times of the two Dirac spikes."""
        return [self.p["mufree"], self.__muset]
        
    
    def set_interp(self):
        """Build the interpolated, normalized PDF for the two spikes."""
        # Width of the Dirac 
        width = max(1, self.get_param_range("mufree") / 200, self.__muset / 200)
        # Finer resolution than convolution 
        td = 1.2 * (self.get_p_max("mufree") + self.__muset) * np.arange(0, 201) / 200
        # Summation of the two Diracs
        pdfd1 = tools_interpolation.dirac_discret(td, center=self.p["mufree"], width=width)
        pdfd2 = tools_interpolation.dirac_discret(td, center=self.__muset, width=width)
        pdfd = self.p["rate"] * pdfd1 + (1 - self.p["rate"]) * pdfd2
        # Interpolation function 
        self.f = tools_interpolation.interp_normalize(td, pdfd)


    def pdf(self, t):
        """Return the probability density function at time ``t``."""
        self.set_interp()
        return self.f(t)
    
    
    def cdf(self, t):
        """Return the cumulative distribution function at time ``t``."""
        return self.p["rate"] * (t > self.p["mufree"]).astype(int) + (1 - self.p["rate"]) * (t > self.__muset).astype(int)
        
       
    def cdf_inv(self, p):
        """Return the inverse CDF (quantile) for probability ``p``."""
        if p < self.p["rate"]:
            return self.p["mufree"]
        else:
            return self.__muset
    
    
    def mean(self):
        """Return the mean of the distribution."""
        return self.p["rate"] * self.p["mufree"] + (1 - self.p["rate"]) * self.__muset
    
    
    def std(self):
        """Return the standard deviation of the distribution."""
        if 0 < self.p["rate"] < 1:
            return np.sqrt(self.p["rate"] * (1 - self.p["rate"]) * (self.__muset - self.p["mufree"]) ** 2)
        else:
            return 1
   
