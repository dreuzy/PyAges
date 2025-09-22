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
import copy

import tools.figures_additional as figadd
import global_parameters as gp       # Global variables
import tracer.tracer_root as tracer


class Convolution(tracer.Tracer): 
    """  
    Convolution of Tracer by lpm 

    Inheritance
    -----------
    Tracer : class
        Class containing all tracer details 

    Attributes, public
    ----------
    
    Attributes, private
    ----------
    __date : float 
        date (year) at which the convlution will be performed
    __prepare : bool
        is convolution prepared ?
    __prepare_times : array of size n
        time at which convolution is pepared
    __prepare_conc : array of size n (same as previous)
        concentrations at which convolution is prepared
    
    Methods (private)
    -------
    __convolution_classic_prepare(self)
        prepares convolution relevant for most distributions between datemin and dateconvol
        resolution is given by gp.RESOLUTION_CONVOLUTION (number of steps)
    __convolution_exp(self,lpm)
        specific convolution for exponential-like distributions
        adapts the discretization to the function discontinuity
    __convolution_dirac(self,lpm)
        specific convolution for Dirac-like distributions
        gets directly the data in the chronicle, no summation for the convolution

    Methods (public)
    -------
    __init__(self,dir_tracer=gp.DIRECTORY_TRACER_DATA,name="",date=2010)
        calls constructor of mother class Tracer
    convolution(self,lpm,prepare=False): 
        Driving convolution function between a lpm and a tracer
    convolution_prepare(self,lpm_type): 
        Prepres Convolution for all lpms except the special cases
    """

    def __init__(self,dir_tracer=gp.DIRECTORY_TRACER_DATA,name="",date=2010):
        """
        Convolution class constructor
        
        Arguments
        ---------
        dir_tracer: str
            Folder in which tracer data should be loaded (when necessary)
        date: float
            Date at which convolution will be computed 
            (possibly one date per tracer, that's why it is stored in this class)
        
        """
        self.__date = date 
        self.__prepare_times = []
        self.__prepare_conc = []
        self.__prepare = False
        # Construction of underlying class Tracer
        tracer.Tracer.__init__(self,dir_tracer,name)


    def get_date(self): 
        """ Accessor of private attribute date """ 
        return self.__date
    
    
    def __convolution_classic_prepare(self,lpm_type): 
        """ 
        Prepres Convolution between datemin and dateconvol 
                                to be performed at date dateconvol
        """   
        # Sampling dates
        if lpm_type == "ig_shifted" : 
            resolution = gp.RESOLUTION_CONVOLUTION
        else:
            resolution = min(25 * gp.RESOLUTION_CONVOLUTION, 5000) 
        dates = self.datemin + (self.__date-self.datemin) * np.arange(0,1,1/resolution)  
        self.__prepare_times = self.__date - dates
        self.__prepare_conc = self.get_concentration(dates,self.__date-dates)


    def __convolution_classic_perform(self,lpm): 
        """ Performs convolution when it is prepared
        """
        convol=-integrate.simpson(self.__prepare_conc * lpm.pdf(self.__prepare_times), x = self.__prepare_times)
        return convol
     
        
    def __convolution_exp(self,lpm): 
        """ Specific convolution for exponential distributions
                Discretization starts at discontinuity
                Refined discretization close to discontinuity
        """
        if lpm.name =="exp": 
            maxdate=self.__date 
        elif lpm.name == "exp_shifted" or lpm.name=="exp_shifted_young" or \
             lpm.name=="exp_shifted_old" or lpm.name == "mix_exp_shifted":
            maxdate=self.__date-lpm.p["shift"]
        mindate=self.datemin
        if maxdate<mindate : 
            convol = 0
        else: 
            sampling = (np.arange(0,1,1/gp.RESOLUTION_CONVOLUTION))**4       
            t2 = maxdate - (maxdate-mindate) * sampling
            convol=-integrate.simpson(self.get_concentration(t2,self.__date-t2) * lpm.pdf(self.__date-t2),x=t2)
        return convol
    
    
    def __convolution_dirac(self,lpm):
        """ Specific convolution for dirac distributions
            Refined discretization close to discontinuity
        """
        if lpm.name == "dirac" or lpm.name == "mix_exp_shifted" :
            # Specific case for which convolution is determined by picking up a value in the chronicle
            time = lpm.get_dirac_time()
            convol = self.get_concentration(self.__date-time,time)
        elif lpm.name == "dirac_double" or lpm.name == "dirac_double_1_set":
            [time1,time2] = lpm.get_dirac_double_time()
            convol1 = self.get_concentration(self.__date-time1,time1)
            convol2 = self.get_concentration(self.__date-time2,time2)
            convol = lpm.p['rate'] * convol1 + (1-lpm.p['rate']) * convol2
        return convol
    
    
    def __convolution_mix_exp_shifted(self,lpm): 
        """ Specific convolution for mixed Dirac and shifted exponential
            Refined discretization close to discontinuity
        """
        convol=lpm.p["rate"] * self.__convolution_dirac(lpm) + (1-lpm.p["rate"]) * self.__convolution_exp(lpm)
        return convol
    
    
    def convolution_prepare(self,lpm_type): 
        """ Prepres Convolution for all lpms except the special cases 
        """
        if lpm_type != "dirac" and lpm_type != "dirac_double" and \
           lpm_type != "dirac_double_1_set" and \
           lpm_type != "exp" and lpm_type != "exp_shifted" and \
           lpm_type != "exp_shifted_young" and \
           lpm_type != "exp_shifted_old" and \
           lpm_type != "mix_exp_shifted":
            self.__convolution_classic_prepare(lpm_type)
            self.__prepare = True
            
    
    def convolution(self,lpm,prepare=False,reg=False,opt=False): 
        """ 
        Driving convolution function between a lpm and a tracer
        
        Arguments
        ---------
        lpm : LPM
            lpm of the convolution 
        prepare : bool
            Additional checks of consistency for preparation status (normally not necessary)
            prepare = False: prepares and preforms convolution
            prepare = True: preforms convolution (preparation completed previously)
        """
        if lpm.name == "dirac" or lpm.name == "dirac_double" or lpm.name == "dirac_double_1_set": 
            # Specific case for which convolution is determined by picking up a value in the chronicle
            convol = self.__convolution_dirac(lpm)
        elif lpm.name == "exp" or lpm.name == "exp_shifted" or \
             lpm.name == "exp_shifted_young" or lpm.name == "exp_shifted_old" :
            # Requires an adapted discretization close to the discontinuity
            convol = self.__convolution_exp(lpm)
        elif lpm.name == "mix_exp_shifted":
            convol = self.__convolution_mix_exp_shifted(lpm)
        else : 
            # For any other distribution, checks preparation status
            if self.__prepare != prepare : 
                print("Problem in the preparation and performance of convolution")
                sys.exit()
            # Prepare convolution if needed
            if self.__prepare == False : 
                self.__convolution_classic_prepare(lpm)
            convol=self.__convolution_classic_perform(lpm)
        
        if opt == True and reg == False and ( lpm.name[-5:]=='young' or lpm.name[-3:]=='old'): 
            # Young: Requires a location larger than the tracer maximum (CFCs, for example)
            # Light Shift of distribution upwards
            lpm2=copy.deepcopy(lpm); lpm2.shift_upward()
            # Recomputes convolution with this shift upward
            convol2 = self.convolution(lpm2,prepare,reg=True)
            # concentration should be lesser than the previous one, otherwise, 
            #   distribution is not on the right side and concentration is modified 
            #   to yield a high convolution product to lead the objective function to the right position
            if lpm.name[-5:]=='young' and convol2<convol : 
                # When distribution is shifted upwards (in time), distribution is aging
                # To get young ages only, 
                convol=200*self.max_value()-convol
            if lpm.name[-3:]=='old' and convol2>convol : 
                # When distribution is shifted upwards (in time), distribution is aging
                # To get young ages only, 
                convol=200*self.max_value()-convol

        return convol


    def convolution_date_range(self,lpm,date1,date2):
        """ Convolution on the range of dates given by [date1,date2]
        Return pandas table
        """ 
        resolution = 50
        date = gp.arange_n(date1,date2,resolution)
        conc=[]
        for i in date:
            self.__date = i
            conc.append(self.convolution(lpm))
        data=[date,conc]
        df=pd.DataFrame(data=data)
        df=df.T
        df.columns=['date','concentration']
        df['element']=self.get_name()
        return df
