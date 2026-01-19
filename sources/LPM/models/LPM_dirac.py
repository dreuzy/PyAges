# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np                      # Arrays
from scipy.stats import expon
from scipy import interpolate        # Interpolation function 

# LPM template
import LPM.core.LPM_root as LPM
import LPM.core.tools_interpolation as tools_interpolation


class LPM_dirac(LPM.LPM):
    """  
    Lumped Parameter Model Dirac


    Methods (additionally to the ones required by abstract mother class)
    -------
    get_dirac_time(self)
        Gets the time of the Dirac, required for efficient convolution 
    
    """

    
    def __init__(self, mu=10, directory_lpm=None):   
        """ Constructor
            Specific
        """
        parameter_values={'mu':mu}
        parameter_units={'mu':'year'}
        LPM.LPM.__init__( self, "dirac", parameter_values, parameter_units, directory_lpm)
                
    
    def get_dirac_time(self):
        """ 
        Returns Dirac time
        """
        return self.p['mu']
        
    
    def set_interp(self):
        """ 
        sets distribution once parameters are loaded 
        #JR: should be checked
        """
        # Width of the Dirac 
        width = max(1,self.get_param_range('mu')/200)
        # A somewhat larger time range than the bounds of the Dirac
        td = 1.2 * self.get_p_max('mu') * np.arange(0,201) / 200
        # Values of the function on the time discretization
        pdfd = tools_interpolation.dirac_discret(td,center=self.p['mu'],width=width)
        self.f = tools_interpolation.interp_normalize(td,pdfd)


    def pdf(self,t):
        """ p=pdf(t)
            Probability Density Function 
            #JR: should be checked
        """
        self.set_interp()
        return self.f(t)
    
    
    def cdf(self,t):
        """ p=cdf(t)
            Cumulative density 
        """
        return (t>self.p['mu']).astype(int)
    

    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        return self.p['mu']
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return(self.p['mu'])
    
    
    def std(self):
        """ 
        Returns std of distribution """
        return(0.)
   
