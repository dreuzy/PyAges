# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: dreuzy
"""

import matplotlib.pyplot as plt      # plt
import numpy as np
import os
import pandas as pd                  # DataFrame
import sys                           # sys: abort code
from scipy import interpolate        # Interpolation function 
from scipy import integrate          # Interpolation function 

import tools.figures_additional as figadd

   
class Tracer: 
    """  
    Chemical element: atom (isotope) or molecule 


    Attributes, public
    ----------
    __name : str
        name of the element (eg: CFC, 3H, Si) 

    Attributes, private
    ----------
    datemin : 
        date minimum at which the tracer concentartion can be computed
    datemax : 
        date maximum at which the tracer concentration can be computed
    __recharge_chronicle : bool
        True: tracer with a chronicle of recharge at the surface provided in a file 
    __recharge_constant : float
        0: no constant recharge    
        >0: onstant value of the racharge at the surface
    __geoproduction: float
        0: no geoproduction 
        >0: value of the rate of geoproduction
    __decay: bool
        True: First-order decay 
    __decay_time: float 
        Characteristic time of decay 
    __unit: str
        Units in which the tracer concentrations are given
    __recharge_chronicle_file: pandas dataframe
        Loaded recharge chronicle of tracer
    __recharge_chronicle_interp: scipy.interpolate.interp1d object
        Interpolator defined from the loaded data
    
    Methods (principal)
    -------
    __init__(dir_tracer,name="",date=2010)
        Constructor:loads characteristics from file 
    get_concentration(self, date, time)
        Gets concentrations at given date and time
        date and time can be scalars or arrays of the same dimension
    """
    def __init__(self,dir_tracer,name=""):
        """
        Tracer Class Constructor from an ensemble of externe files
        
        Args:
            dir_tracer: str
                root directory where the tracers are stored
                default defined in the file global_parameters.py
            name: str
                tracer name 
            date: float
                year of reference for the tracer #JR: what is precisely 
        """
        # Name of tracer (e.g. cfc11, kr85)
        self.__name = name
        
        # Loads file to get the main tracer characteristics
        table = pd.read_csv( dir_tracer + name + "\\" + name + ".txt",header=None)
        
        # Sets characteristics of tracers from loaded file
        self.__recharge_constant = 0
        self.__recharge_chronicle = 0
        self.__geoproduction = 0
        self.__decay = 0
        self.__decay_time = -1
        self.datemin = -1
        self.datemax = -1
        for i in range(len(table)): 
            check = 0
            if table.iloc[i,0] == 'recharge_constant': 
                self.__recharge_constant = table.iloc[i,1]
                check = 1
            if table.iloc[i,0] == 'recharge': 
                self.__recharge_chronicle = table.iloc[i,1]
                check = 1
            if table.iloc[i,0] == 'production rate':
                self.__geoproduction = 1
                self.__geoproduction_rate = table.iloc[i,1]
                check = 1
            if table.iloc[i,0] == 'decay characteristic time':
                self.__decay = 1
                self.__decay_time = table.iloc[i,1]
                check = 1
            if table.iloc[i,0] == 'unit':
                self.__unit = table.iloc[i,2]
                check = 1
            if table.iloc[i,0] == 'datemin':
                self.datemin = table.iloc[i,1]
                check = 1
            if table.iloc[i,0] == 'datemax':
                self.datemax = table.iloc[i,1]
                check = 1
            if check == 0:
                print("ERROR LOADING THE TRACER PARAMETERS-ABORTING")
                sys.exit()
        
        # Loads recharge chronicle 
        if(self.__recharge_chronicle):
            self.__recharge_chronicle_file = pd.read_table(dir_tracer + name + "\\recharge.txt",header=0)
            # Creation of interpolation function for the input chronicle
            self.__recharge_chronicle_interp = interpolate.interp1d(self.__recharge_chronicle_file.iloc[:,0], self.__recharge_chronicle_file.iloc[:,1],kind="linear")
            # min and max date of input chronicle
            self.datemin = min(self.__recharge_chronicle_file.iloc[:,0])
            self.datemax = max(self.__recharge_chronicle_file.iloc[:,0])
        
        # Checks that data are correctly provided
        if self.datemin == -1 : 
            print("critical error when loading tracers, datemin not defined"); sys.exit()
        if self.datemax == -1 : 
            print("critical error when loading tracers, datemax not defined"); sys.exit()
            
                
    def get_unit(self):
        """ Accessor of private attribute unit """ 
        return self.__unit
    
    
    def get_name(self): 
        """ Accessor of private attribute unit """ 
        return self.__name
    
    
    def __check_date_range(self, date):
        """ Checks that date is in adminissible range, whether it is a scalar or an array
        """
        if isinstance(date, np.ndarray):
            return not (any(date>self.datemax) or any(date<self.datemin))
        else: 
            return (date<=self.datemax) and (date>=self.datemin)


    def get_concentration(self, date, time):
        """ 
        Computes concentrations of tracers 
        
        Args
            date: float or array
                date(s) at which concentrations are computed
                date - time : date of recharge for the input chronicle
            time: 
                times(s) corresponding at which concentrations are computed
                time necessary for decay and geoproduction
        
        Raises
            error when date is out of range [datemin,datemax] for the preparation of convolution
        
        Returns
            c: array of floats
                concentations at the given date and time
        """
        c = 0
        if self.__recharge_chronicle or self.__recharge_constant:
            if self.__recharge_chronicle : 
                if self.__check_date_range(date) == True : 
                    # Recharge concentrations obtained by interpolation
                    c1 = self.__recharge_chronicle_interp(date)
                else: 
                    if isinstance(date, np.ndarray):
                        test = (date >= self.datemin) * (date <= self.datemax)
                        c1 = date * 0 
                        for i in range(len(test)): 
                            if(test[i]): 
                                c1[i] = self.__recharge_chronicle_interp(date[i])
                    else: 
                        c1=0
            elif(self.__recharge_constant): 
                # constant recharge concentrations, creates vector of the required size
                c1 = self.__recharge_constant * time**0
            if(self.__decay):
                # Decay applied to the recharge chronicle
                c1 = c1 * np.exp(- time / self.__decay_time)
            c = c + c1 
        if(self.__geoproduction):
            if(self.__decay):
                c2 = self.__geoproduction_rate * (1-np.exp(- time / self.__decay_time)) * self.__decay_time
            else: 
                c2 = self.__geoproduction_rate * time
            c = c + c2
        return c


    def mean_value(self,date):
        """ Mean value of chronicle taken at date "date"
        """    
        # Sampling dates
        t = self.datemin + (date-self.datemin) * np.arange(0,1,1/1000)        
        # computes convolution 
        return np.mean(self.get_concentration(t,date-t))        


    def display(self,display_options):
        """ Display chemical element
        """
        if display_options.text : print("chemical:", self.__name)
        # plotting the input chronicle
        if self.__recharge_chronicle == True : 
            self.__recharge_chronicle_file.plot(x=self.__recharge_chronicle_file.columns[0],y=self.__recharge_chronicle_file.columns[1],title="input chronicle (recharge) for " + self.__name)
            display_options.figure_close_fx(self.__name+"_recharge")
        # extracting the data
        date = np.linspace(self.datemin,self.datemax,1000)
        time = self.datemax - date
        c = self.get_concentration(date, time)
        # plot of the data
        figadd.figure_init(xlab='date',ylab='concentrations',figname=self.__name)
        plt.plot(date, c, 'r', label=self.__name)
        display_options.figure_close_fx(self.__name+"_chronicle")

        

