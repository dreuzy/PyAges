# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Legacy shifted-exponential LPM variant kept for backward compatibility.
Uses the classic LPM base class with explicit parameters.
"""


# Statistical distributions
import numpy as np                      # Arrays
from random import uniform
from scipy.stats import expon

# LPM template
from LPM.core.LPM_root import LPM
from LPM.models.LPM_exp_shifted import LPM_exp_shifted            # LPM shifted exponential


class LPM_exp_shifted_old(LPM_exp_shifted):
    """ Lumped Parameter Model
        Exponential
    """
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
        
        

    
