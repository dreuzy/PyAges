# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: dreuzy
"""

# Plots
import os
import numpy as np
import pandas as pd                                         
import sys

import global_parameters as gp
import convolutions.convolution as convolution               
import LPM.LPM_generate as LPM_generate
import convolutions.concentrations as concentrations


class ConvolutionTracers: 
    """  
    Convolution method organized along the list of tracers
    Mostly a vector of "Convolution" class instances 


    Attributes, public
    ----------
    elements : array of Convolution class instances
        tracers and convolution method    
        almost everything is in element
    
    Attributes, private
    ----------
    
    Methods (principal)
    -------
    __init__(self,names=["cfc11","kr85"],date=2010)
        calls constructor of convolution and tracer
    """
    
    def __init__(self,names=["cfc11","kr85"],date=2010):
        """ 
        Constructor
        
        Arguments
        ---------
        names: array of str
            name of tracers to be loaded
        """
        # Create element list and loads each element
        if(np.isscalar(date)): date_temp = [date] * len(names)
        else : date_temp = date
        self.elements = []
        k = 0
        for x in names:
            self.elements.append(convolution.Convolution(name=x,date=date_temp[k]))
            k=k+1
    
    
    def display(self,display_options):
        """ 
        Displays the tracers
        """
        for x in self.elements:
            x.display(display_options)
    
        
    def write_name(self,file):
        file.write("tracers")
        for t in self.element_names() :
            file.write('\t')
            file.write(t)
        file.write('\n')


    def element_names(self): 
        """ 
        Gets the list of element names 
        """
        names = []
        for x in self.elements:
            names.append(x.name)
        return names


    def element_names_dates(self): 
        """ 
        Gets the list of element names 
        """
        names = []
        for x in self.elements:
            names.append(concentrations.name_date(x.name, x.get_date()))
        return names
    
    
    def mean_value(self,date):
        """ 
        Mean value of chronicle Taken at "date"
        Parameters
            date (float):date
        Rerunrs 
            mv (array of floats):mean value for each of the element concentrations sampled from date "date"
        """
        mv = []
        for x in self.elements:
            mv.append(x.mean_value(date))
        return mv
    
    
    def convolution_prepare(self,lpm_type): 
        """ 
        Prepares Convolution at date "date"
        """
        for t in self.elements:
            t.convolution_prepare(lpm_type)

    
    def units(self):
        """ 
        Gets units of tracers
        Returns
            List of units 
        """
        units=[]
        for t in self.elements:
            units.append(t.unit)
        return units        

    
    def convolution(self,lpm,return_type="array",prepare=False,opt=False): 
        """ 
        Convolution between a lpm and the tracers at given date 
        
        Parameters: 
            lpm (LPM): LPM with which convolution is made
            date (float): date of convolution 
            return_type (str): format of convolution return
        
        Returns:
            array if return_type=="array"
            concentrations_set if return_type=="concentrations_set"
            dataframe if return_type=="dataframe"
        """
        # Performs convolution 
        conc=[]; date_vec=[]
        for t in self.elements:
            conc.append(t.convolution(lpm,prepare=prepare,opt=opt))
            date_vec.append(t.get_date())
        # Translates in the required format
        if return_type=="array":
            data = conc
        elif return_type=="concentrations_set":
            data_temp = pd.DataFrame({"element": self.element_names(), "concentration": conc, "unit": self.units(), "date":date_vec}, columns = ["element", "concentration", "unit", "date"])
            data = concentrations.Concentrations(dataframe_load=True,dataframe_concentration=data_temp)
        elif return_type=="dataframe_columns":
            data = pd.DataFrame(columns=self.element_names())
            data.loc[len(data.index)] = conc
        elif return_type=="dataframe":
            data = pd.DataFrame({"element": self.element_names(), "concentration": conc, "date": date_vec}, columns = ["element", "concentration"])
        else:
            print('Error option unknown in convolution', return_type)
        return data
    
    
    def convolution_date_range(self,lpm,date1,date2):
        """ 
        Convolution on the range of dates given by [date1,date2]
        Return list of pandas table
        """ 
        conc={}
        for t in self.elements:
            conc[t.name]=t.convolution_date_range(lpm,date1,date2)
        return conc



def write_file_conc_lpm(date,concentrations,lpm,directory):
    """ 
    Write the tracers in the files
    #JR: definition in concentration classes rather than here? 
    """
    # Write date and lpm    
    name_tracers = ""
    for t in concentrations.iloc[:,0]: name_tracers = name_tracers + "_" + t
    root_name = os.path.join(directory,"convol_" + lpm.name + "_" + name_tracers)
    file = open(root_name +" _lpm" + ".txt", "w")
    file.write("date\t")
    file.write(str(date))
    file.write("\n")
    lpm.write(file,open_file=False)
    file.close()
    # Write concentrations
    concentrations.to_csv(root_name +" _concentrations" + ".txt",sep='\t') #, header=None, index=None, sep=',', mode='w')


def test_load_and_display(element_types,display_options):
    """ Test concentration loading
    """
    date = 2010
    # Chemical Elements
    tracers=ConvolutionTracers(names=element_types,date=date)
    if display_options.figure : 
        tracers.display(display_options)
    
    
def test_convolution(lpm_name,tracer_names,display_options,date=2000):
    """ 
    Test convolution function 
        Randomly chosen lpm
    
    Parameters
    ----------
    lpm_name: str
        Name of lpm
    tracer_names: array of str
        List of names of tracers to be convoluted
    display_options: display_options
        Figure and Text display options
    date: float
        date (year) at which convolution is taken 
    
    """
    
    # Randomly choosen lpm
    rng=np.random.default_rng(12345)
    lpm = LPM_generate.LPM_generate_random_uniform(lpm_name,rng=rng)
    # Convolution definition w/ tracer loading
    tracers = ConvolutionTracers(names=tracer_names,date=date)
    # Convolution w/ results as a concentrations set
    concentrations = tracers.convolution(lpm,return_type="concentrations_set",prepare=False)
    # Dislays lpm and resulting concnetrations
    if display_options.text : 
        print('convolution as concentration_sets')
        lpm.display(display_options)
        concentrations.display(display_options)
    # Convolution w/ results as a DataFrame 
    concentrations = tracers.convolution(lpm,return_type="dataframe",prepare=False)
    if display_options.text : 
        print('convolution as dataframe')
        print('date', date)
        print(concentrations)
   # Write results in file  
    write_file_conc_lpm(date,concentrations,lpm,display_options.directory)
    