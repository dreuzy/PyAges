# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np
from scipy.stats import gamma

# LPM template
from LPM.core.LPM_root import LPM
       

class LPM_gamma(LPM):
    """ Lumped Parameter Model
        Gamma
    """
    def __init__(self, k=2, scale=10, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'k':k,'scale':scale}
        parameter_units={'k':'','scale':'year'}
        LPM.__init__(self,"gamma",parameter_values,parameter_units, directory_lpm)
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return gamma.pdf(t, self.p['k'], 0, self.p['scale'])
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return gamma.cdf(t, self.p['k'], 0, self.p['scale'])


    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        return gamma.ppf(p,self.p['k'],scale=self.p['scale'])
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return abs(gamma.stats(self.p['k'],scale=self.p['scale'],moments='m'))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(np.sqrt(gamma.stats(self.p['k'],scale=self.p['scale'],moments='v')))
    
