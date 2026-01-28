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

from LPM.core.LPM_root import LPM
from LPM.core.convolution_strategy import ConvolutionStrategy
from LPM.core.registry import register_lpm
from LPM.models.LPM_exp_shifted import LPM_exp_shifted


@register_lpm("exp_shifted_young")
class LPM_exp_shifted_young(LPM_exp_shifted):
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
        LPM.__init__(self, "exp_shifted_young", parameter_values, parameter_units, directory_lpm)
    

    def shift_upward(self): 
        """ Shift the distribution upward
            Used to determine position of the distribution compared to the peak of cfcs
        """
        self.p['mu']=self.p['mu']*1.1
        
        

    
