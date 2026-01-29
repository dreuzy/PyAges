# -*- coding: utf-8 -*-
"""
LPM Mixed Shifted-Exponential distribution model.

Purpose
-------
Define a mixture combining a Dirac-like spike with a shifted exponential
tail, used to represent bimodal travel time distributions.

Author
------
Jean-Raynald de Dreuzy
"""

import math

from scipy.stats import expon

from LPM.core.LPM_root import LPM
from LPM.core.convolution_strategy import ConvolutionStrategy
from LPM.core.registry import register_lpm


@register_lpm("mix_exp_shifted")
class MixExponentialShiftedLpm(LPM):
    """Lumped Parameter Model - Mixed shifted exponential distribution."""

    convolution_strategy = ConvolutionStrategy.MIX_DIRAC_EXPONENTIAL

    def __init__(self, rate=0.5, mu1=10, mu2=10, shift=20, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        rate : float
            Mixing weight for the Dirac component (0 to 1).
        mu1 : float
            Location of the Dirac spike (years).
        mu2 : float
            Scale parameter for the exponential component.
        shift : float
            Shift for the exponential component.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {'rate': rate, 'mu1': mu1, 'mu2': mu2, 'shift': shift}
        parameter_units = {'rate': '-', 'mu1': 'year', 'mu2': 'year', 'shift': 'year'}
        LPM.__init__(self, "mix_exp_shifted", parameter_values, parameter_units, directory_lpm)
        
        
    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
        """
        return (1-self.p['rate']) * expon.pdf(t,loc=self.p['mu1']+self.p['shift'],scale=self.p['mu2'])
    
    
    def get_dirac_time(self):
        """ 
        returns Dirac time
        """
        return self.p['mu1']
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return self.p['rate'] * (t>self.p['mu1']).astype(int) + (1-self.p['rate']) * expon.cdf(t,loc=self.p['mu1']+self.p['shift'],scale=self.p['mu2'])

    
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        #JR: should be checked
        """
        r = self.p['rate']
        if p < r : 
            return self.p['mu1']
        else: 
            return self.p['mu1'] + self.p['mu1'] + self.p['shift'] - self.p['mu2'] * math.log((p-r)/(1-r)) 
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        #JR: To implement
        return self.p['rate'] * self.p['mu1'] + (1-self.p['rate']) * (self.p['shift'])
    
    
    def std(self):
        """ 
        Returns std of distribution """
        #JR: To implement
        return 0
    
    
