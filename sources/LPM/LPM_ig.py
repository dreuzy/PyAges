# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: dreuzy
"""


# Statistical distributions
import numpy as np
from scipy.stats import invgauss

# LPM template
from LPM.LPM_root  import LPM
       

class LPM_ig(LPM):
    """ Lumped Parameter Model
        Inverse Gaussian
        Reference, e.g. 
            Waugh, D., and T. Hall (2002), Age of stratospheric air: 
            Theory, observations, and models, Reviews of Geophysics, 40(4), 1-1-1-26, 
            doi:https://doi.org/10.1029/2000RG000101.
    """
    def __init__(self, mu=10, sigma=2, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu,'sigma':sigma}
        parameter_units={'mu':'year','sigma':'year'}
        LPM.__init__(self,"ig",parameter_values,parameter_units,directory_lpm)
        
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return invgauss.pdf(t, self.p['mu'], 0, self.p['sigma'])
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return invgauss.cdf(t, self.p['mu'], 0, self.p['sigma'])
    
    
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
        return invgauss.ppf(p_safe, self.p['mu'], scale=self.p['sigma'])
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return abs(invgauss.stats(self.p['mu'],scale=self.p['sigma'],moments='m'))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(np.sqrt(invgauss.stats(self.p['mu'],scale=self.p['sigma'],moments='v')))
    
