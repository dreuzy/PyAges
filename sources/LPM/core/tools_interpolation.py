# -*- coding: utf-8 -*-
"""
Created on Mon May 24 17:03:47 2021

@author: Jean-Raynald de Dreuzy
"""


from scipy import interpolate        # Interpolation function 



def interp_normalize(td,pdfd): 
    """
    Normalization of interpolation function 
    
    Arguments
    ---------
    td: array
        time discrete
    pdfd: array
        pdf values at time td 
        
    Returns
    -------
    fd: interpolator
        interpolation function 
    """
    fd = interpolate.interp1d(td,pdfd)
    # Ensures integral to one
    step_size = td[1] - td[0]               
    sumftd=sum(fd(td)*step_size)
    if sumftd != 0 : 
        fd = interpolate.interp1d(td,pdfd/sumftd)
    else: 
        print("problem in set_interp of LPM Dirac") 
    # sum(fd(td)*step_size)
    return fd


def dirac_discret(t,center=1,width=1): 
    """
    Discrete values of Dirac function 
        =1 for t in [center-width/2,center+width/2]
        =0 otherwise
    
    Arguments
    ---------
    td: array
        discrete time
    center: float
        center of the Dirac
    width: float
        width of the Dirac
        
    Returns
    -------
    fd: array
        discrete values of Dirac
    """
    return ((t >= center - width / 2) * (t <= center + width / 2)).astype(int) / width
