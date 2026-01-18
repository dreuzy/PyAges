# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: dreuzy
"""

import copy as copy
import os
import numpy as np
import pandas as pd    
import matplotlib.pyplot as plt                                     
import sys

import global_parameters as gp                              # Global variables


def name_date(name,date): 
    """ Combination of name and date """
    temp=name + "-" + str("{:.{}f}".format( date, 1))
    temp=temp.replace(".","_")
    return temp


class Concentrations:
    """  
    Concentrations list 
        List of concentratiosn elements
        No specific algorithm

    Attributes, public
    ----------
    cv : dataframe 
        concentrations
        example of cv dataframe
            element	concentration	error	unit	date
            cfc11	139.0	        20.0	pptv	2010.0
            kr85	40.0	          5.0	pptv	2010.0
    
    Attributes, private
    ----------
    
    Methods
    -------
    error_affectation(self,mean_value,fraction=0.01)
        Affects errors to fraction (scalar) * mean_value (vector)
    error_affect_from_mean(self,mean_value,fraction=0.01)
        define errors proportional to the mean tracer concentrations
    error_affect_from_value(self,fraction):
        define errors proportional to the concentration values
    sample_concentrations_with_errors(self,rng)
        Samples concentrations from the distribution of errors given
    sqrt_quadratic_mean_diff(self,c2)
        Computes sqrt of quadratic mean differnces of self.cv and c2.cv    
      
    """
    def __init__(self,file_load=False,file_name="",dataframe_load=False,dataframe_concentration=pd.DataFrame()):
        """
        Constructor
        
        Arguments
        ---------
        file_load: bool
            concentrations loaded from file #JR: obsolete?
        file_name: str
            name of file from which concentrations are loaded
        dataframe_load: bool
            concentrations derived from dataframe
        dataframe_concentration: dataframe
            concentration dataframe
    
        """
        test = 0
        if file_load == True :
            # Loads data from file
            self.__load_file(file_name)
            test = 1
        if dataframe_load == True :
            # Concentrations from dataframe
            self.cv = dataframe_concentration
            test = 1
        if test == 0 :
            print("\n Problem in loading/initializing Concentrations")
        # Definition of errors
        self.__error_definition()
        # Definition of units
        self.__unit_definition()
        # Checks consistency of the data
        self.__check_consistency()


    def __load_file(self,file_name):
        """
        Loads concentrations data from file
        
        Arguments
        ---------
            file_name: str
                name of file
        """
        # Creates and reads data
        self.cv = pd.read_table(file_name,sep="\t",header=0)


    def __error_definition(self):
        """
        If errors are not defined, adds column errors = 0 to the data
        """
        if not "error" in self.cv.columns:
            self.cv["error"]=0


    def error_affect_from_mean(self,mean_value,fraction=0.01):
        """
        Error affectation 
            define errors proportional to the mean tracer concentrations
            error = fraction * mean_value
        
        Arguments
        ---------
            mean_value: array
                mean_value of tracer chronicle
            fraction: float
                fraction of the mean value to define the error
        """
        for i in range(len(self.cv.values[:,gp.ERROR])):
            if self.cv.iloc[i,gp.ERROR] == 0 :
                self.cv.iloc[i,gp.ERROR] = mean_value[i] * fraction


    def error_affect_from_value(self,fraction):
        """
        Error affectation 
            define errors proportional to the concentration values
            error = fraction * concentration_value
        
        Arguments
        ---------
            fraction: float
                fraction of the mean value to define the error
        """
        self.cv = self.cv.astype({'error':float})
        self.cv.iloc[:,gp.ERROR] = np.float64(fraction * self.cv.values[:,gp.CONCENTRATION])


    def __unit_definition(self):
        """
        If units are not defined, set units to mol/l
        """
        if not "unit" in self.cv.columns:
            self.cv["unit"]="mol/l"
            

    def __check_consistency(self):
        """
        Checks the consistency of the concentration data
            Checks that all reference names in gp.REFERENCE_COLUMNS are well defined in concentrations data
            Puts columns in the order given by gp.REFERENCE_COLUMNS
        """
        # Checks the column names
        error = 0
        for i in range(len(gp.REFERENCE_COLUMNS)):
            if (gp.REFERENCE_COLUMNS[i] in self.cv.columns) == False :
                print('\n\Column named is not defined and should be\t',gp.REFERENCE_COLUMNS[i])
                error = 1
        if error :
            print("critical error in the definition of concentrations")
            # sys.exit()
        # Ensures that columns are in the right order
        self.cv = self.cv[gp.REFERENCE_COLUMNS]


    def sample_concentrations_with_errors(self,rng) :
        """ 
        Samples concentrations from the distribution of errors given
        
        Arguments
        ---------
        rng: 
            Random Number Generator
            
        Returns
        -------
        conc: Concentrations 
            concentrations generated from the underlying distribution of errors
        """
        conc = copy.deepcopy(self)
        # Loop on each of the elements
        for i in range(len(conc.cv.values[:,gp.CONCENTRATION])):
            # Gets concentration from normal distribution
            conc.cv.iloc[i,gp.CONCENTRATION] = self.cv.values[i,gp.CONCENTRATION] + self.cv.values[i,gp.ERROR] * rng.standard_normal()
        return conc


    def sqrt_quadratic_mean_diff(self,c2):
        """ 
        Computes sqrt of quadratic mean differnces of self.cv and c2.cv
        
        Arguments
        ---------
        c2: Concentrations 
            Concentrations of same strucutre as self
            
        Returns
        -------
        float
            square root of quadratic mean difference
        """
        return np.sqrt(sum(np.square(self.cv.values[:,gp.CONCENTRATION]-c2.cv.values[:,gp.CONCENTRATION])/len(c2.cv.values[:,gp.CONCENTRATION])))


    def display(self,display_options):
        """ Display chemical element
        """
        if display_options.text == True :
            print(self.cv)


    def figure_concentrations(self, i1, i2): 
        plt.scatter(self.cv['concentration'][i1],self.cv['concentration'][i2],marker='o',c='r',s=150)


    def names(self):
        """ Gets tracer names
        """
        names =[]
        for i in range(len(self.cv.iloc[:,0])):
            names.append(self.cv.iloc[i,0])
        return names


    def names_dates(self):
        """ Gets tracer names + dates
        """
        names =[]
        for i in range(len(self.cv.iloc[:,0])):
            names.append(self.cv.iloc[i,0]+"_"+str(self.cv.loc[i]['date'])+"_"+str(i))
        return names
    

    def names_list(self):
        """ Gets tracer names in a str chain
        """
        name = None
        for t in self.names():
            name = name + "_" + t
        return name


    def export_to_dict(self): 
        """ Export concentrations to dictionary """
        data={}
        for i in range(len(self.cv.iloc[:,0])):
            data[self.cv.iloc[i,0]]=self.cv.iloc[i,gp.CONCENTRATION]
        return data
    
    
    def cv_key_name_date(self): 
        """ 
        Export data with key element-date in place of element 
        
        Input
        -----
              element  concentration    error   unit  date
              0   cfc11       0.000000  1.05258   pptv  1990
              1      Li      70.411685  2.11235  mol/l  2010
        
        Returns
        -------
              element  concentration    error   unit  date
              0  cfc11-1990       0.000000  1.05258   pptv  1990
              1     Li-2010      70.411685  2.11235  mol/l  2010
        """
        cv=self.cv.copy()
        for iterrow, row in cv.iterrows():
            rowa=dict(row)
            cv.loc[iterrow,'element']=name_date(rowa['element'],rowa['date'])
        return cv
        
        

def test_load(file_name,display_options=False):
    """ 
    Test Concentartions Data Loading
        Display loaded concentrations 
    
    Arguments
    ---------
        file_name: str
            name from which data should be loaded
        display_options: display_options (global_parameters)
            determines the figures and texts to display
    """
    # Loads test data
    c_data=Concentrations(file_load=True, file_name=str(gp.DIRECTORY_TEST / file_name))
    # Displays test data
    c_data.display(display_options)
