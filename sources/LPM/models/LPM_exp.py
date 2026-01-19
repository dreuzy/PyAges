# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np                      # Arrays
from scipy.stats import expon

# LPM template
from LPM.core.LPM_root import LPM

class LPM_exp(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, mu=10, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu}
        parameter_units={'mu':'year'}
        LPM.__init__( self, "exp", parameter_values, parameter_units, directory_lpm)
        
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return expon.pdf(t, 0, self.p['mu'])
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return expon.cdf(t, 0, self.p['mu'])
    
    
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        return expon.ppf(p,scale=self.p['mu'])
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return abs(expon.stats(scale=self.p['mu'],moments='m'))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(np.sqrt(expon.stats(scale=self.p['mu'],moments='v')))
    


