# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy
"""


# Statistical distributions
import numpy as np                      # Arrays

# LPM template
from LPM.core.LPM_root import LPM
import LPM.core.tools_interpolation as tools_interpolation


class LPM_dirac_double_1_set(LPM):
    """ Lumped Parameter Model
        Exponential
    """
    def __init__(self, mufree=10, muset=70, rate=0.2, directory_lpm=None):   
        """ Constructor
            Specific
        """
        self.__muset=70
        parameter_values={'mufree':mufree,'rate':rate}
        parameter_units={'mufree':'year','rate':''}
        LPM.__init__( self, "dirac_double_1_set", parameter_values, parameter_units, directory_lpm)
                
    
    def get_dirac_double_time(self):
        """ 
        returns Dirac time
        """
        return [self.p['mufree'],self.__muset]
        
    
    def set_interp(self):
        """ 
        sets distribution once parameters are loaded 
        """
        # Width of the Dirac 
        width = max(1,self.get_param_range('mufree')/200,self.__muset/200)
        # Finer resolution than convolution 
        td = 1.2 * (self.get_p_max('mufree')+self.__muset) * np.arange(0,201) / 200
        # Summation of the two Diracs
        pdfd1 = tools_interpolation.dirac_discret(td,center=self.p['mufree'],width=width)
        pdfd2 = tools_interpolation.dirac_discret(td,center=self.__muset,width=width)
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
        return self.p['rate'] * (t>self.p['mufree']).astype(int) + (1-self.p['rate']) * (t>self.__muset).astype(int)
        
       
    def cdf_inv(self,p):
        """ Inverse of the Cumulative Density Function, t=cdf^-1(p)
        """
        if p < self.p['rate'] :
            return self.p['mufree']
        else : 
            return self.__muset
    
    
    def mean(self):
        """ 
        Returns mean of distribution """
        return( self.p['rate'] * self.p['mufree'] + (1-self.p['rate']) * (self.__muset))
    
    
    def std(self):
        """ 
        Returns std of distribution """
        if (self.p['rate']>0 and self.p['rate']<1):
            return( np.sqrt(self.p['rate']*(1-self.p['rate'])*(self.__muset-self.p['mufree'])**2))
        else:
            return 1
   