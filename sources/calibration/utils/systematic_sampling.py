# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy
"""


import copy
from itertools import combinations
from math import ceil
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd                                         # DataFrame
from scipy.interpolate import RegularGridInterpolator
import sys

import global_parameters as gp
import tools.figures_additional as figadd
from convolution.convolution_tracers import ConvolutionTracers
from LPM.LPM_generate import LPM_generate
from calibration.utils.objective_functions import L2_norm_diff


class ParamSysSampling: 
    """ 
    Systematic sampling of parameters in the range of pmin-pmax
        Cartesian Product whatever the number of model parameters (<=4)
        Treats the different dimension cases 1,2,3,4
    It only stores the parameter structure, not the data
        data values, should be external as several type of data can be processed 
        with the same structurel: computed concentrations and objective function
            
    Attributes
    ----------
    __np: int
        Number of parameters to vary for the cartesian product 
    __p: matrix of int
        parameters sampled in the different directions
    __nmodels: int
        total number of models to investigate
    __n: int
        number of parameter sampled in the different dimensions (equal in all dimensions)
    __pnames: list of str
        Parameter names
        
    Methods for processing parametes (INTERNAL): lists and indices
    --------------------------------------------------------------
    plist(self)
        Returns list of parameters such as an array [param[i],param[j],param[k]]
        Same order as __pindices
    __pindices(self)
        Returns list of indices such as an array [i,j,k]        
        Same order as plist
    __pdimensions(self)
        Returns dimensions in the different parameter directions [ni,nj,nk]
    __nparams(self)
        Total number of parameter sets = Total number of models run
    display(self)
        Displays on command line the class 
        
    Methods for processing values (EXTERNAL): format, interpolation and display
    ---------------------------------------------------------------------------
    grid_data(self,data):
        data[(p(i),p(j),p(k))]->val_array(i,j,k)
    __interp(self,val_array)
        (p(i),p(j),p(k)) and val_array(i,j,k) -> interp
    __display_1D(self,Xp,Z,display_options,name_fig,xlabel="")
        Dislay 1D Z=f(Xp)
        Including figure initialization and termination
    __display_2D(self,Xp,Yp,Z,display_options,name_fig,xlabel="",ylabel=""):
        Dislay 2D Z=f(Xp,Yp)
        Including figure initialization and termination
    
    """
    
    def __init__(self,pmin,pmax,nmodels,pnames): 
        """ Systematic sampling in the range of pmin-pmax
                Cartesian Product
            Parameters
            ----------
            pmin: array of floats
                vector of min for each of the dimensions to investigate 
            pmax: array of floats
                vector of max for each of the dimensions to investigate
            nmodels: int
                total number of models to investigate
        """
        # Number of parameters to vary for the cartesian product
        self.__np = len(pmin)
        # Total number of models to investigate
        self.__nmodels = nmodels
        # Resolution in each of the dimentions (parameters) to investigate
        self.__n = ceil(nmodels**(1/self.__np))
        # Storage of sampling in all the dimensions
        self.__p = [None]*self.__np
        # Parameter names
        self.__pnames = pnames
        # Cartesian Product for the different dimension cases 
        for i in range(self.__np):
            self.__p[i] = gp.arange_n(pmin[i],pmax[i],self.__n) 
        # self.__write()
      
    
    def __nparams(self): 
        """ Returns number of parameter sets """
        n=1
        for i in range(self.__np): 
            n=n*len(self.__p[i])
        return n
    
    
    def set_nmodels(self,nmodels): 
        """ sets nmodels (private) from outside the class """
        self.__nmodels = nmodels
    
    
    def __write(self): 
        """ Displays sampled parameters in the different dimensions
        """
        print("Number of dimensions sampled:", self.__np)
        print("Number of models sampled:", self.__nmodels)
        print("Number of parameters sampled in each dimensiont:", self.__n)
        print("Total number of parameter sets investigated:", self.__nparams)
        print("List of parameters sampled in each dimension")
        np.set_printoptions(formatter={'float': '{: 0.2f}'.format})
        for i in range(self.__np):
            print(self.__pnames[i])
            print(self.__p[i])
        print(self.__pindices())
        
    
    def plist(self): 
        """ Sets list such as an array of [i,j,k] """
        if self.__np == 1:
            return [[i] for i in self.__p[0]]
        elif self.__np == 2:
            return [[i,j] for i in self.__p[0] for j in self.__p[1]]
        elif self.__np == 3:
            return [[i,j,k] for i in self.__p[0] for j in self.__p[1] for k in self.__p[2]]
        elif self.__np == 4:
            return [[i,j,k,l] for i in self.__p[0] for j in self.__p[1] for k in self.__p[2] for l in self.__p[3]]
        else: 
            print('problem in ParamSysSampling with np', self.__np)
            sys.exit()
            
            
    def __pindices(self): 
        """ Returns equivalent list of indices """
        if self.__np == 1:
            return [[i] for i in range(len(self.__p[0]))]
        elif self.__np == 2:
            return [[i,j] for i in range(len(self.__p[0])) for j in range(len(self.__p[1]))]
        elif self.__np == 3:
            return [[i,j,k] for i in range(len(self.__p[0])) for j in range(len(self.__p[1])) for k in range(len(self.__p[2]))]
        elif self.__np == 4:
            return [[i,j,k,l] for i in range(len(self.__p[0])) for j in range(len(self.__p[1])) for k in range(len(self.__p[2])) for l in range(len(self.__p[3]))]
        else: 
            print('problem in ParamSysSampling with np', self.__np)
            sys.exit()
            
    
    def __pdimensions(self): 
        """ Returns dimensions of array in the different sampling directions
        """
        if self.__np == 1:
            return (len(self.__p[0]))
        elif self.__np == 2:
            return (len(self.__p[0]),len(self.__p[1]))          
        elif self.__np == 3: 
            return (len(self.__p[0]),len(self.__p[1]),len(self.__p[2]))        
        elif self.__np == 4: 
            return (len(self.__p[0]),len(self.__p[1]),len(self.__p[2]),len(self.__p[3]))        
        
        
    def grid_data(self,data):
        """
        Transforms list of values on grid of values
            Returns data[(p(i),p(j),p(k))]->val_array(i,j,k)
        
        Inputs 
        -------
        self.__p: list of arrays
            parameter values
        val: array
            data values, should be external as several type of data can be processed 
            with the same structurel: computed concentrations and objective function
        
        Returns
        -------
            val_array(i,j,k)
        """
        # Creates interpolator
        if self.__nparams() != len(data): 
            print("Pb in interp of ParamSysSampling")
            sys.exit()
        # [i,j,k]
        indices=self.__pindices()
        val_array = np.zeros(self.__pdimensions(),dtype=float)
        for i in range(self.__nparams()): 
            val_array[tuple(indices[i])]=data[i]
        # Returns list of parameter arrays and values
        return [tuple(self.__p),val_array]

        
    def __interp(self,val_array): 
        """ 
        Returns interpolator based on the data 
            Requires the run of grid_data before
            (p(i),p(j),p(k)) and val_array(i,j,k) -> interp
            
        Inputs
        ------
        val_array: array of floats
            array of values to interpolate (size self.__nparams())
            same dismensions as self.__p
            
        Returns 
        -------
        Interpolator
        """
        # Interpolator in itself
        return RegularGridInterpolator(tuple(self.__p),val_array)
    
    
    def __display_1D(self,Xp,Z,display_options,name_fig,xlabel="",lpm_results=None):
        """
        Dislay 1D Z=f(Xp) 
            Including figure initialization and termination
        
        Inputs
        ------
        Xp: array of floats
            parameters 
        Z: array of floats
            values
        display_options: Class display_options
            display 
        name_fig: str
            figure name 
        xlabel: str
            label of x
        """
        figadd.figure_init(figname=name_fig)
        plt.plot(Xp,Z)
        plt.xlabel(self.__pnames[0])
        plt.yscale("log")    
        if lpm_results != None : 
            lpm_results.display_param_vs_param(self.__pnames[0],"obj_function")
        display_options.figure_close_fx(name_fig)
        

    def __display_2D(self,Xp,Yp,Z,display_options,name_fig,xlabel="",ylabel="",lpm_results=None):
        """
        Dislay 2D Z=f(Xp,Yp)
            Including figure initialization and termination
        
        Inputs
        ------
        Xp: array of floats
            parameters 0
        Yp: array of floats
            parameters 1 
        Z: array of floats
            values
        display_options: Class display_options
            display 
        name_fig: str
            figure name 
        xlabel: str
            label of x
        ylabel: str
            label of y
        """
        figadd.figure_init(figname=name_fig)
        X,Y=np.meshgrid(Xp,Yp)
        plt.pcolor(X,Y,Z,cmap=figadd.cmap_white_jet())
        plt.xlabel(ylabel); plt.ylabel(xlabel)
        plt.colorbar()
        if lpm_results != None : 
            lpm_results.display_param_vs_param(ylabel,xlabel)
        display_options.figure_close_fx(name_fig)
    
    
    def display_grid_data(self,grid_data,display_options,name_fig="",lpm_name="exp_shifted",lpm_results=None): 
        """ 
        Displays grid_data(i,j,k)=f(p(i),p(j),p(k)) 
        
        Inputs
        ------
        grid_data: array of floats
            grid_data[i][j][k] ... 
        display_options: Class display_options
            display 
        name_fig: str
            figure name 
        """
        if self.__np == 1 : 
            # 1D graph
            self.__display_1D(self.__p[0],grid_data,display_options,name_fig,
                            xlabel=self.__pnames[0],lpm_results=lpm_results)
        elif self.__np == 2 : 
            # 2D colormap
            if(lpm_name=="exp_shifted" or lpm_name=="exp_shifted_young" or \
               lpm_name=="exp_shifted_old" or lpm_name=="uniform" or \
               lpm_name=="dirac_double_1_set"): 
                index0=0; index1=1; 
            else: 
                index0=1; index1=0; 
            self.__display_2D(self.__p[index0],self.__p[index1],grid_data,display_options,name_fig,
                            xlabel=self.__pnames[index0],ylabel=self.__pnames[index1],lpm_results=lpm_results)
        elif self.__np == 3 : 
            # interpolation function
            fn_interp=self.__interp(grid_data)
            # 2D colormap for all successive parameter combinations
            for k0 in range(self.__np-1):
                k1 = (k0+1)%self.__np
                k2 = (k0+2)%self.__np
                Z = np.zeros((len(self.__p[k0]),len(self.__p[k1])))
                ptemp=[None]*self.__np
                for i in range(len(self.__p[k0])):
                    for j in range(len(self.__p[k1])):
                        ptemp[k0]=self.__p[k0][i];ptemp[k1]=self.__p[k1][j];ptemp[k2]=self.__p[k2][int(len(self.__p[k2])/2)]
                        Z[i][j] = fn_interp(ptemp)[0]
                self.__display_2D(self.__p[k0],self.__p[k1],Z,display_options,name_fig + "_" + str(k0),
                                xlabel=self.__pnames[k0],ylabel=self.__pnames[k1])
        
    
class SystematicSampling:
    """ 
    Determination of reachable concentrations by systematic sampling parameter space
        Builds a DataFrame with 
            the concentrations as colums of the DataFrame
            the models as lines of the DataFrame
        Associated with the ParamSysSampling class for the management of parameters and indices
    
    Attributes (public)
    ----------
    display: display_options
        Display otpions

    Attributes (private)
    ----------
    __tracers: ConvolutionTracers
        tracers involved in the analysis
    __lpm: LPM
        Template LPM structure 
    __nmodels: int 
        Number of models to run (resolution)
    __date: float 
        Date (year) at which the analysis is performed
    __cdata: Concentrations Class
        Concentrations Data
    __psystsampling: ParamSysSampling
        Systematic Sampling of parameters within the boundary defined in parameter files
    __concentrations: dataframe
        Concentrations computed with systematic sampling
    __obj_function: dataframe
        Objective function, same organization as __Concentrations
    
    Methods (public)
    ----------------
    compute_concentrations(self)
        Systematical sampling of parameters
        Computes corresponding concentrations ("reachable concentrations")
    display_concentrations_with_data(self,data=None,imax=10)
        Displays concentrations agains each other (points in the concentration space representation)
        Add data for comparison if aviailable
    output(self)
        Output in file of "reachable concentrations"        
    analysis_reach_conc(self): 
        Analysis of reachable concentrations
    analysis_calibration(self): 
        Analysis of the calibration problem
    """
    
    def __init__(self,lpm_name,tracer_names,date=2010,nmodels=1000,
                 cdata=None,objfunc=True,reachconc=True,
                 display_options=None):
        """ 
        Parameters
        ----------
            lpm_name: str
                name of lpm
            tracer_names: array of str
                name of tracers
            nmodels: int
                Number of models to run
            date: float
                Date (year) at which the analysis is performed
            cdata: Concentrations Class
                Concentrations data (optional)
            display_options: None or display_options
                if None, affectation by default
            objfunc: bool 
                Should objective function be displayed
            reachconc: bool 
                Should reachable concentrations be displayed
        """
        # Builds tracer_chemicals
        self.__tracers=ConvolutionTracers(names=tracer_names,date=date)
        # Builds lpm
        self.__lpm = LPM_generate(lpm_name)
        # Sets nmodels 
        self.__nmodels = nmodels
        # Sets date
        self.__date = date
        # Sets concentrations data
        self.__cdata = cdata
        # Sets display options
        self.display = display_options
        # Should concentrations be displayed
        self.display_reachconc = reachconc
        # Range of parameters
        pmin,pmax=self.__lpm.get_param_interval()
        # List of parameter sets
        self.__psystsampling = ParamSysSampling(pmin,pmax,self.__nmodels,[*self.__lpm.p])
        # Concentration dataframe
        self.__concentrations = None
        
        
    def compute_concentrations(self):
        """
        Computes concentrations on the grid of parameter sets
        """
        # List of parameter sets
        params = self.__psystsampling.plist()        
        # List of concentrations computed
        tracer_names_elts = self.__tracers.element_names_dates()
        data = np.zeros((len(params),len(tracer_names_elts)))
        # Preparation of convolution 
        self.__tracers.convolution_prepare(self.__lpm.name)
        # For each of the parameter set in the list, computes the corresponding concentration
        for i in range(len(params)):
            # Modification of parameters in lpm & convlution computation
            self.__lpm.set_param_from_array(params[i])
            data[i,:] = self.__tracers.convolution(self.__lpm,prepare=True,opt=True)
        # Stores results in a dataframe
        self.__concentrations = pd.DataFrame(data=data,columns=tracer_names_elts)
        

    def display_concentrations_with_data(self,imax=10):
        """ 
        Displays Results
        
        Parameters 
        ----------
        data: Concentrations (optional)
            data that should be calibrated 
        imax: int 
            Displays a maximum of "imax" figures
        """
        # Retrieves combinations of tracers
        comb = combinations(range(len(self.__concentrations.columns)), 2)
        # Displays the "imax" first combinations
        for co, i in zip(comb, range(imax)) :
            tracer_name_0=self.__concentrations.columns[co[0]]
            tracer_name_1=self.__concentrations.columns[co[1]]
            # Figure Initialization
            # figadd.figure_init(xlab=tracer_name_0 + "_" + str(int(self.__date[co[0]])), \
            #                    ylab=tracer_name_1 + "_" + str(int(self.__date[co[1]])), \
            #                    figname='reachable_'+tracer_name_0+'_'+tracer_name_1)
            figadd.figure_init(xlab=tracer_name_0, ylab=tracer_name_1, \
                               figname='reachable_'+ tracer_name_0 + '_' + tracer_name_1)
            # Displays Model
            plt.scatter(self.__concentrations.iloc[:,co[0]],
                        self.__concentrations.iloc[:,co[1]],marker='+',c='b',s=10)
            # Displays Data
            if self.__cdata != None : self.__cdata.figure_concentrations(co[0],co[1])
            # Figure Termination
            # self.display.figure_close_fx("c_reach" + tracer_name_0 + "_" + str(int(self.__date[co[0]])) + "_" +  \
            #                                            tracer_name_1 + "_" + str(int(self.__date[co[1]])))
            self.display.figure_close_fx("c_reach" + tracer_name_0 + "_" + tracer_name_1)
                

    def output(self): 
        """
        Results Outputs
        """
        # Parameters
        f = open(os.path.join(self.display.directory_results,"parameters.txt"), "w")
        f.write("date\t")
        f.write(str(self.__date))
        f.write("\n")
        self.__lpm.write_name(f)
        self.__tracers.write_name(f)
        f.write("nmodels\t")
        f.write(str(self.__nmodels))
        f.write("\n")
        f.close()
        # Reachable concentrations
        self.__concentrations.to_csv(os.path.join(self.display.directory_results,"c_reach.txt"),sep='\t') #, header=None, index=None, sep=',', mode='w')


    def objective_function_build(self): 
        """ 
        Objective Function determination by systematically sampling the parameter space 
            By default, the resolution is self.nmodels
        Objective Function should be defined exactly like in common
        Assumes that both arrays are organized in the same way
            data: rows
            model: columns
        Examples: 
            data
                           element  concentration    error   unit  date
                   0        cfc11-1990_0   0.000000  1.05258   pptv  1990
                   1        Li-2010_0      70.411685  2.11235  mol/l  2010 
            model
                               cfc11-1990_0  Li-2010_0
                   0           267.654   0.000000
                   1           267.654   0.000000
                   2           267.654   0.000000
                   3           267.654   0.000000
                   4           267.654   0.000000
        Inputs
        ------
        display_options: Class display_options
            Figure management
        """
        # Retrieves concentration data
        dfdata=self.__cdata.cv_key_name_date()
        # Retrieves concentration model
        dfmodel=self.__concentrations
        # Checks consistency of data formats
        if dfdata.shape[0] != dfmodel.shape[1] : 
            print("Pb in objective_function_build Arrays of different sizes"); sys.exit()
        # Computes objective function from previously computed concentrations
        ojf=0
        for colmod, idat in zip(dfmodel.transpose().iterrows(), range(dfdata.shape[0])):
            # Checks element consistency
            if colmod[0] != dfdata.loc[idat]['element'] : 
                print("Pb in objective_function_build Different element names"); sys.exit()
            # Effective objective function computation
            ojf=ojf+L2_norm_diff(dfdata.loc[idat]['concentration']*np.ones(dfmodel.shape[0]),
                                              colmod[1].to_numpy(),dfdata.loc[idat]['error'])
        # Sqrt of mean quadratic differences divided by error
        ojf = np.asarray(ojf, dtype=float)
        # Avoid log(0) when objective values are zero
        ojf = np.maximum(ojf, np.finfo(float).tiny)
        ojf = 0.5 * np.log(ojf)
        # Storage in a dataframe
        self.__obj_function = pd.DataFrame(
            np.hstack((np.asarray(self.__psystsampling.plist()), np.transpose([ojf]))),
            columns=[*self.__lpm.p.keys(), "log-ojf"],
        )
        

    def objective_function_display(self,lpm_results=None):
        """ Dsplays objective function 
        """
        # Grids objective function 
        [p_grid,obj_function_grid]=self.__psystsampling.grid_data(self.__obj_function['log-ojf'])
        # Displays gridded data
        self.__psystsampling.display_grid_data(
            obj_function_grid,
            self.display,
            name_fig="objfun_of_" + self.__lpm.name,
            lpm_name=self.__lpm.name,
            lpm_results=lpm_results,
        )


    def set_nmodels(self,nmodels): 
        """ sets nmodels (private) from outside the class """
        self.__psystsampling.set_nmodels(nmodels)


    def analysis_reach_conc(self): 
        """ Analysis of reachable concentrations
        """
        # Computes concentrations on the grid of parameter sets
        self.compute_concentrations()
        # Displays concenrations in 2D plots
        if self.display_reachconc : 
            self.display_concentrations_with_data()


    def analysis_calibration(self,lpm_results=None): 
        """
        Analysis of the calibration problem
            Computation of reachale concentrations
            Objective Function if concentration data aviailable
            Figures and Storage
        Synthesis of the key methods of the class
            Methods can be called and used alternatively 
        """
        # Computes concentrations on the grid of parameter sets
        self.compute_concentrations()
        # Displays concenrations in 2D plots
        if self.display_reachconc : 
            self.display_concentrations_with_data()
        # Computes Objective Function 
        self.objective_function_build()
        # Displays Objective Function in 2D plots
        self.objective_function_display(lpm_results)



def test_reachconc(lpm,tracer_names,display_options,nmodels=1000,date=2010):
    """ 
    Test Reachable concentration operations
    """
    # Directory name for outputs
    name_tracers = ""
    for t in tracer_names: name_tracers = name_tracers + "_" + t
    display_options_cr=copy.deepcopy(display_options)
    display_options_cr.directory_results = gp.results_directory(display_options.directory, "reach" + name_tracers + "_" + lpm)
    # Reachable concentrations per se
    cr = SystematicSampling( lpm, tracer_names, date=[date]*len(tracer_names), nmodels=nmodels, display_options=display_options_cr, reachconc=True)
    cr.compute_concentrations()
    cr.analysis_reach_conc()
