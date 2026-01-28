# -*- coding: utf-8 -*-
"""
LPM Shifted Exponential (legacy) distribution model.

Purpose
-------
Legacy shifted-exponential LPM variant kept for backward compatibility.
Uses the classic LPM base class with explicit parameters.

Author
------
Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np                      # Arrays
from random import uniform
from scipy.stats import expon

# LPM template
from LPM.core.LPM_root import LPM
from LPM.models.LPM_exp_shifted import LPM_exp_shifted            # LPM shifted exponential


class LPM_exp_shifted_old(LPM_exp_shifted):
    """Lumped Parameter Model - Shifted Exponential (legacy) distribution."""
    def __init__(self, mu=10, shift=10, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu,'shift':shift}
        parameter_units={'mu':'year','shift':'year'}
        LPM.__init__( self, "exp_shifted_old", parameter_values, parameter_units, directory_lpm)
    
    
    def shift_upward(self): 
        """ Shift the distribution upward
            Used to determine position of the distribution compared to the peak of cfcs
        """
        self.p['mu']=self.p['mu']*1.1
        
        

    
