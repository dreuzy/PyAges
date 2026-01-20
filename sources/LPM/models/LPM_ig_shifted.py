# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np
from scipy.stats import invgauss

# LPM template
from LPM.core.LPM_root import LPM
       

class LPM_ig_shifted(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, mu=10, sigma=2, shift=5, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu,'sigma':sigma,'shift':shift}
        parameter_units={'mu':'year','sigma':'year','shift':'year'}
        LPM.__init__(self,"ig_shifted",parameter_values,parameter_units, directory_lpm)
        

    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return invgauss.pdf(t, self.p['mu'], self.p['shift'], self.p['sigma'])
    

    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return invgauss.cdf(t, self.p['mu'], self.p['shift'], self.p['sigma'])


    def cdf_inv(self, p):
        """Inverse of the Cumulative Density Function, t = cdf^-1(p).
    
        Parameters
        ----------
        p : float or array-like
            Probability value(s) between 0 and 1.
    
        Returns
        -------
        float or ndarray
            Quantile(s) of the inverse Gaussian distribution.
        """
        eps = 1e-12  # marge de sécurité
        p_safe = np.clip(p, eps, 1 - eps)
        return invgauss.ppf(
            p_safe,
            self.p['mu'],
            scale=self.p['sigma'],
            loc=self.p['shift']
        )
    

    def mean(self):
        """ 
        Returns mean of distribution """
        return abs(invgauss.stats(self.p['mu'],scale=self.p['sigma'],loc=self.p['shift'],moments='m'))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(np.sqrt(invgauss.stats(self.p['mu'],scale=self.p['sigma'],loc=self.p['shift'],moments='v')))
    
