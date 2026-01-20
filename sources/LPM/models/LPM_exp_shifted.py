# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np                      # Arrays
from random import uniform
from scipy.stats import expon

# LPM template
from LPM.core.LPM_root import LPM


class LPM_exp_shifted(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, mu=10, shift=10, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu,'shift':shift}
        parameter_units={'mu':'year','shift':'year'}
        LPM.__init__( self, "exp_shifted", parameter_values, parameter_units, directory_lpm)
        
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return expon.pdf(t, self.p['shift'], self.p['mu'])
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return expon.cdf(t, self.p['shift'], self.p['mu'])
    
    
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        return expon.ppf(p,scale=self.p['mu'],loc=self.p['shift'])
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return abs(expon.stats(scale=self.p['mu'],loc=self.p['shift'],moments='m'))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(np.sqrt(expon.stats(scale=self.p['mu'],loc=self.p['shift'],moments='v')))
    
