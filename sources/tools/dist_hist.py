# -*- coding: utf-8 -*-
"""
Created on Mon May 24 17:03:47 2021

@author: dreuzy
"""
import matplotlib.pyplot as plt
import matplotlib        as mpl
import os
from pylab import *


class dist_hist:
    """  
    Distribution of parameter values

    Attributes, public
    ----------

    Attributes, private
    ----------

        
    Methods 
    -------

    """

    def __init__(self,names,values):
        """ 
        Constructor for the distribution of parameters
        """
        self.__names = names
        self.__values = values

            