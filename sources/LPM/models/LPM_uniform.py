# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
from scipy.stats import uniform as uniform_stats
import numpy as np

# LPM template
from LPM.core.LPM_root import LPM
       

class LPM_uniform(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'tmin':2,'delta':10}
        parameter_units={'tmin':'year','delta':'year'}
        LPM.__init__(self,"uniform",parameter_values,parameter_units,directory_lpm)
        
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return uniform_stats.pdf(t, self.p['tmin'], self.p['delta'])
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return uniform_stats.cdf(t, self.p['tmin'], self.p['delta'])

        
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        return self.p['tmin'] + p * self.p['delta']
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return self.p['tmin'] + self.p['delta'] /2
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return np.sqrt((self.p['delta'])**2/12)
    

