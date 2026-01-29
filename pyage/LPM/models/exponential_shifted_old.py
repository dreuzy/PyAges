# -*- coding: utf-8 -*-
"""
LPM Shifted Exponential (old-water) distribution model.

Purpose
-------
Shifted exponential LPM variant biased toward older ages.
Extends the shifted exponential model with an upward shift helper.

Author
------
Jean-Raynald de Dreuzy
"""

from pyage.LPM.core.lpm_base import LpmBase
from pyage.LPM.core.convolution_strategy import ConvolutionStrategy
from pyage.LPM.core.registry import register_lpm
from pyage.LPM.models.exponential_shifted import ExponentialShiftedLpm


@register_lpm("exp_shifted_old")
class ExponentialShiftedOldLpm(ExponentialShiftedLpm):
    """Lumped Parameter Model - Shifted Exponential (old-water) distribution."""

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
        LpmBase.__init__(self, "exp_shifted_old", parameter_values, parameter_units, directory_lpm)
    
    
    def shift_upward(self): 
        """ Shift the distribution upward
            Used to determine position of the distribution compared to the peak of cfcs
        """
        self.p['mu']=self.p['mu']*1.1
        
        

    
