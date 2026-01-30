# -*- coding: utf-8 -*-
"""
LPM Shifted Exponential (young-water) distribution model.

Purpose
-------
Shifted exponential LPM variant biased toward younger ages.
Extends the shifted exponential model with an upward shift helper.

Author
------
Jean-Raynald de Dreuzy
"""

from pyage.lpm.core.lpm_base import LpmBase
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.core.registry import register_lpm
from pyage.lpm.models.exponential_shifted import ExponentialShiftedLpm


@register_lpm("exp_shifted_young")
class ExponentialShiftedYoungLpm(ExponentialShiftedLpm):
    """Lumped Parameter Model - Shifted Exponential (young-water) distribution."""

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
        LpmBase.__init__(self, "exp_shifted_young", parameter_values, parameter_units, directory_lpm)
    

    def shift_upward(self): 
        """ Shift the distribution upward
            Used to determine position of the distribution compared to the peak of cfcs
        """
        self.p['mu']=self.p['mu']*1.1
        
        

    
