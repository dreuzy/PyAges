# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Double-Dirac LPM model with two spikes separated by mu2 and mixed by rate.
Builds a discretized, normalized PDF for convolution.
"""


# Statistical distributions
import numpy as np                      # Arrays
from scipy.stats import expon
from scipy import interpolate        # Interpolation function 

# LPM template
from LPM.core.LPM_root import LPM
import LPM.core.tools_interpolation as tools_interpolation


class LPM_dirac_double(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, mu1=10, mu2=5, rate=0.2, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu1':mu1,'mu2':mu2,'rate':rate}
        parameter_units={'mu1':'year','mu2':'','rate':''}
        LPM.__init__( self, "dirac_double", parameter_values, parameter_units, directory_lpm)
                
    
    def get_dirac_double_time(self):
        """ 
        returns Dirac time
        """
        return [self.p['mu1'],self.p['mu1']+self.p['mu2']]
        
    
    def set_interp(self):
        """ 
        sets distribution once parameters are loaded 
        """
        # Width of the Dirac 
        width = max(1,self.get_param_range('mu1')/200,self.get_param_range('mu2')/200)
        # Finer resolution than convolution 
        td = 1.2 * (self.get_p_max('mu1')+self.get_p_max('mu2')) * np.arange(0,201) / 200
        # Summation of the two Diracs
        pdfd1 = tools_interpolation.dirac_discret(td,center=self.p['mu1'],width=width)
        pdfd2 = tools_interpolation.dirac_discret(td,center=self.p['mu1']+self.p['mu2'],width=width)
        pdfd = self.p['rate'] * pdfd1 + (1-self.p['rate']) * pdfd2 
        # Interpolation function 
        self.f = tools_interpolation.interp_normalize(td,pdfd)


    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function
            #JR: should be chekced
        """
        self.set_interp()
        return self.f(t)
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return self.p['rate'] * (t>self.p['mu1']).astype(int) + (1-self.p['rate']) * (t>self.p['mu1']+self.p['mu2']).astype(int)
        
       
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        if p < self.p['rate'] :
            return self.p['mu1']
        else : 
            return self.p['mu2']
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return( self.p['rate'] * self.p['mu1'] + (1-self.p['rate']) * (self.p['mu1']+self.p['mu2']))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return( np.sqrt(self.p['rate']*(1-self.p['rate'])*(self.p['mu2'])**2))
   
