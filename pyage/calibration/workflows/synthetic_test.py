# -*- coding: utf-8 -*-
"""
Created on Tue May 18 21:14:24 2021

@author: Jean-Raynald de Dreuzy
"""
import copy
import numpy as np
import os
import pandas as pd

import pyage.convolution.convolution_tracers as convolution_tracers                     
import pyage.global_parameters as gp
import pyage.LPM.lpm_build as lpm_build_module

import pyage.calibration.utils.calibration_core as calbas

from pyage.concentrations import concentrations_time as ct


class CalibrationSyntheticTest:
    """ 
    Synthetic Testing of Calibration algorithms 
        For any type of lpm
        1. Generates a lpm
        2. Computes synthetic concentrations by convolution of the tracer at the given date
        3. Definition of error for these syntetic "data" using a dedicated random number generator (for reproductibility)
        4. Use these data to calibrate a lpm of the same type with the calibration properties defined in self.__calib_strategy
    
    Attributes
    ----------
    __tracer_names: array of str
        Name of tracers with which the test will be performed 
    __date: array of floats
        Dates at which the tracers are taken (one date per tracer, should be repeated for identical dates)
    __lpm_type: str
        Type of lpm, active only when lpm_option == "random"
    __ncase: int
        Number of synthetic cases handled 
    __error: float
        Level of errors to add to the synthetic data (in fraction, eg 0.01 is 1%)
    __display_options: display_options class
        includes folder to store results
    __nmodels: int
        number of models for the parameter sampling
    __calib_strategy: Simplex, MetropolisHastings
        Daughter Class of CalibrationCore
        Only the methods of mother class CalibrationCore will be called 
        
    Methods (public)
    ----------------
    perform_one_case(self,i,lpm_random=True,lpm_target=None)
        Performs case "i"
    perform_ncase(self):
        Performs n cases and writes synthetic results  
    get_directory(self): 
        Accessor to self.__directory  
    write_parameters_test(self)
        Write tracer nammes, callibration methods and calibration parameters
    write_results(self)
        Write synthesis results for all n tests
    
    Methods (private)
    -----------------
    __storage_one_case(self,lpm_target,lpm_calib,i)
        Storage of results in dataframe
    
    """
    
    def __init__(self,calib_strategy=None,ncase=10,error=1.0,
                 lpm_type='exp',tracer_names=["cfc11","kr85"],date=2010, nmodels=10000,
                 display_options=gp.display_options(),directory = "test_calibration_"):
        """ 
        Constructor
            Attribute affectations
            Initialization of rng, tracers, storage structure
        
        Parameters
        ----------
        lpm_type: str
            Type of lpm, active only when lpm_option == "random"
        tracer_names: array of str
            Name of tracers with which the test will be performed 
        """
        # Attribute affectations
        self.__lpm_type = lpm_type
        self.__tracer_names = tracer_names
        self.__ncase = ncase
        self.__error = error
        self.__date = date
        self.__seed_rng = 1234
        self.__calib_strategy = calib_strategy
        self.__nmodels = nmodels
        
        # Storage of test results
        self.__display_options = copy.deepcopy(display_options)
        # Storage directory
        self.__display_options.directory = gp.results_directory(self.__display_options.directory,
                                                self.__calib_strategy.method + "_" + self.__lpm_type)
        # Initialization of random number generator
        self.rng = np.random.default_rng(self.__seed_rng)
        # Initialization of tracers
        self.tracers = convolution_tracers.ConvolutionTracers(names=self.__tracer_names,date=self.__date)
        
        # Initialization of test storage sructure 
        self.store = pd.DataFrame(columns=['case','error_concentration_%','objective_mean',
                                           'objective_std','parameter_name','target',
                                           'estim_mean','estim_std','estim_min','estim_max',])
                       
        
    def __storage_one_case(self,lpm_target,lpm_calib,i):
        """ 
        Storage of results in dataframe
        """
        # Statistics on results of parameters 
        data = {'case':i}
        lpm_calib.get_stats_line(lpm_target,data)
        # Adds new line
        if i == 0:
            self.store = pd.DataFrame(data)
        else:
            self.store=pd.concat([self.store,pd.DataFrame(data)])   
    
        
    def get_directory(self): 
        """ Accessor to self.__directory """
        return self.__display_options.directory
    
        
    def write_results(self):
        """ 
        Write synthesis results for all n tests
        File Example: 
            #JR 06/08: Revoir la documentation des résultats synthétiques 
            	case	mu_target	            mu_difference	 scale_target	scale_difference	mu_count	mu_mean	mu_std	mu_min	mu_25%	mu_50%	mu_75%	mu_max	scale_count	scale_mean	scale_std	scale_min	scale_25%	scale_50%	scale_75%	scale_max	obj_function_count	obj_function_mean	obj_function_std	obj_function_min	obj_function_25%	obj_function_50%	obj_function_75%	obj_function_max
        0	    0	   78.13831135918156		30.477639228067464		0.0								0.0								0.0							
        0	    1	   73.86737407774004		21.009224666697182		0.0								0.0								0.0							
        0	    1	   73.86737407774004		21.009224666697182		0.0								0.0								0.0							

        """
        self.store.to_csv(os.path.join(self.__display_options.directory,"results.txt"),sep='\t')
        self.store.describe().to_csv(os.path.join(self.__display_options.directory,"results_stats.txt"),sep='\t')
        
        
    def write_parameters_test(self):
        """ 
        Write tracer nammes, callibration methods and calibration parameters
        File Example: 
            error	       0.01
            date	       [1990, 2010]
            calibration_method	Simplex
            lpm_type	   ig
            tracer_0	   cfc11
            tracer_1	   Li
        """
        data={}
        data['error']=self.__error
        data['date']=self.__date
        data['calibration_method']=self.__calib_strategy.method
        data['lpm_type']=self.__lpm_type
        comp = 0
        for t in self.__tracer_names:
            data['tracer_'+str(comp)]=t
            comp = comp + 1
        file = open(os.path.join(self.__display_options.directory,"parameters.txt"),"w")
        for key, val in data.items():
            file.write(key+'\t'+str(val)+'\n')
        file.close()

        
    def perform_one_case(self,i,lpm_random=True,lpm_target=None):
        """ 
        Performs one test case with either target lpm or a randomly generated lpm
        
        Arguments
        ---------
        i: int
            lable of test case
        lpm_random: bool 
            True: generate a LPM
            False: takes the provided lpm lpm_target
        lpm_target: LPM
            Target LPM 
        
        Returns
        -------
        lpm_target: LPM
            Target LPM models 
        cdata
            Concentration Synthetic "data"
        __calib_strategy
            Calibration strategy
        lpm_results: LPM_dist
            Calibrated distribution of lpms
        distance
            Euclidean distance between target parameters and estimated mean
        """
        # display_options to be used for this case with specific directory  (no change in generic display_options)
        display_options_case = copy.deepcopy(self.__display_options)
        display_options_case.directory = gp.results_directory(display_options_case.directory,str(i))
        
        # 1. TARGET LPM: If not provided, generates a lpm
        if lpm_random == True : 
            lpm_target = lpm_build_module.lpm_build_random_uniform(self.__lpm_type, rng=self.rng)
        else: 
            if lpm_target.name != self.__lpm_type : 
                print("Inconsistency between lpm_target and lpm_type, replacement")
                self.__lpm_type = lpm_target.name
        
        # 2. TARGET CONCNETRATIONS: Computes synthetic concentrations by convolution of the tracer at the given date, concentration set with this lpm
        cdata = self.tracers.convolution(lpm_target,return_type="concentrations_set",prepare=False)
        # Adds some percentage of uncertainty to these syntetic "data" using a dedicated random number generator (for reproductibility)
        cdata.error_affect_from_value(self.__error)
        
        # 3. CALIBRATION : Use these data to calibrate a lpm of the same type with the calibration properties defined in __calib_strategy
        calib_basis=calbas.CalibrationCore(cdata,self.__lpm_type,display_options=display_options_case,nmodels=self.__nmodels)
        calib_basis.prepare()
        # Updates parent class CalibBasis of __calib_strategy (with new cdata)
        self.__calib_strategy.update_calibbasis(calib_basis)
        # 4a. Performs calibration
        lpm_results = self.__calib_strategy.perform()
        # 4b. Analysis of Calibration Problem (reachable concentrations and objective function)
        self.__calib_strategy.analysis_calibration(lpm_results)
        
        # 5. POSTPROCESSING
        # Displays and Writes target and calibrated lpms
        self.__calib_strategy.display_lpms(self.__display_options,lpm_results,lpm_reference = lpm_target)
        lpm_target.write(os.path.join(display_options_case.directory,"lpm_target.txt"),open_file=True)
        self.__calib_strategy.write_calibrated_lpm(lpm_results)
        cdata.cv.to_csv(os.path.join(display_options_case.directory,"concentrations.txt"),sep='\t')
        # Concentration chronicles with time
        ct.display_concentration_chronicles(cdata,lpm_results,str(i),self.__display_options,time_span_mode="suc",lpm_number=10)
        # Results storage
        self.__storage_one_case(lpm_target,lpm_results,i)
        # Distance between target and estimated parameters (mean of distribution)
        try:
            stats = lpm_results.get_stats()
            keys = list(lpm_target.p.keys())
            target_vals = np.array([lpm_target.p[k] for k in keys], dtype=float)
            estim_vals = np.array([stats.loc['mean'][k] for k in keys], dtype=float)
            distance = float(np.linalg.norm(estim_vals - target_vals))
        except Exception:
            distance = float("nan")
        return lpm_target, self.__calib_strategy, cdata, lpm_results, distance
        

    def perform_ncase(self):
        """ 
        Performs n cases and writes synthetic results
        """
        distances = []
        for i in range(self.__ncase):
            [_,lpm_calibration,_,_,distance] = self.perform_one_case(i)
            distances.append(distance)
        # Writes synthetis on parameters and results
        lpm_calibration.write_parameters(os.path.join(self.__display_options.directory,"parameters_calibration.txt"))
        self.write_parameters_test()
        self.write_results()
        if distances:
            return float(np.nanmean(distances))
        return float("nan")
            
        
