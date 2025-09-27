# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: dreuzy
"""

import numpy as np
import os

from calibration.calibration_exploration import ParamSysSampling, CalibrationExploration, objective_function
import global_parameters as gp                         
import LPM.LPM_generate as LPM_generate                                        
import convolutions.convolution_tracers as convolution_tracers      
import convolutions.concentrations as co 

from pathlib import Path

def folder_prior_posterior(file, stageup=-5, folder_prior=""): 
    """Folder in which posteriors will be stored to use later as priors.

    Parameters
    ----------
    file : str or Path
        Path of a file or directory used as reference.
    stageup : int
        Index relative to the parent parts (default = -5).
        Example: -1 = parent, -2 = grand-parent, etc.
    folder_prior : str
        Subfolder name for the prior distributions.

    Returns
    -------
    Path
        Path to the created folder.
    """
    file_path = Path(file).resolve()
    
    # on remonte de |stageup| niveaux
    try:
        folder_root = file_path.parents[abs(stageup) - 1]
    except IndexError:
        raise ValueError(f"stageup={stageup} remonte trop haut pour {file_path}")
    
    # sous-dossier prior_distributions
    folder_root = folder_root / "prior_distributions"
    folder_root.mkdir(parents=True, exist_ok=True)

    # sous-dossier optionnel folder_prior
    if folder_prior:
        folder_root = folder_root / folder_prior
        folder_root.mkdir(parents=True, exist_ok=True)
    
    return folder_root


def file_prior_posterior(file_ploemeur, error_concentrations, lpm_type): 
    return file_ploemeur+"_err_"+str(error_concentrations)+"_lpm_"+lpm_type


class CalibrationBasis(CalibrationExploration): 
    """ 
    Class for the calibration of a LPM of type LPM_type on sampled concentrations in "cdata
        Only the formulation of the problem 
        Calibration methods are defined in daughter classes 
        
    Inherits
    --------
    CalibrationExploration
        Exploration of the concentrations and objective function 
        In the parameter space 
        Not systematically activated
    
    Attributes
    ----------
    cdata: Concentrations
        target concentrations 
    lpm: LPM
        lpm that will be calibrated 
    tracers: ConvolutionTracers
        Tracers and Convolution method (affected by the constructor)
    
    Methods
    -------
    objective_function(self, param, data_c, data_error, conc=False)
        objective function computation from param
        ||(model_concentrations(param)-data_c)^2/data_error^2||^1/2
    display_concentrations(self)
    
    
    """

    def __init__(self,cdata,LPM_type,display_options=gp.display_options(),directory_lpm=gp.directory_lpm_data,
                 nmodels=1000,objfunc=True,reachconc=True):
        """ 
        Constructor
        
        Parameters
        ----------
        cdata: Concentrations
            target concentrations and dates at which they were taken
        LPM_type: str
            type of LPM, which will be calibratited (e.g. exp,ig,gamma)
        display_options: display_options class
            Patrameters for the storage of results
        directory_lpm: str
            Directory of lpm details #JR 05/08: no longer used? Obsolete
        nmodels: int 
            Number of models to be tested for reachable concentrations and objective function
        objfunc: bool 
            Should Objective Function be displayed
        reachconc: bool
            Should Reachable Concentrations be displayed
        """
        
        self.cdata = cdata
        # Initiation of the LPM structure (not the targeted parameters)
        self.lpm = LPM_generate.LPM_generate(LPM_type,directory_lpm)
        # Initiation of the tracer_chemicals corresponding to the data sampled
        self.tracers = convolution_tracers.ConvolutionTracers(names=self.cdata.cv.iloc[:,0],date=self.cdata.cv['date'])
        # Definition of errors (if error == 0, takes mean chronicle value): 
        # Should be performed here because requires the date to be performed
        #JR-modification: specify date for mean_value
        self.cdata.error_affect_from_mean(self.tracers.mean_value(self.cdata.cv['date'].mean()))
        # Prepration of convolution 
        self.tracers.convolution_prepare(self.lpm.name)
        # Directory for storage (eg MH trajectory)
        self.display_options = display_options
        # self.__dict__.update(calparam.__dict__)
        CalibrationExploration.__init__(self,LPM_type,self.cdata.names(),date=self.cdata.cv["date"],
                                      cdata=cdata,nmodels=nmodels,objfunc=objfunc,reachconc=reachconc,
                                      display_options=self.display_options)
    
    
    def objective_function(self, param, data_c, data_error, conc=False):
        """ 
        Objective Function: Squared difference of concentrations normalized by data errors
            Inverse Problem Theory and Methods for Model Parameter Estimation, Albert Tarantola, SIAM, 2005
            http://www.ipgp.fr/~tarantola/Files/Professional/Books/InverseProblemTheory.pdf
            sum((di-mi)^2/sigma_errori^2)
        
        Arguments
        --------
        param: array
            array of parameter values (order should correspond to that of the lpm)
        concentrations_sampled_c: array
            target concentrations
        concentrations_sampled_error: array
            target concentrations errors
        lpm: LPM
            template LPM (parameters are updated with param)
        tracers: ConvolutionTracers
            convolution class 
        conc: bool
            True: returns also the concentrations
            
        Returns
        -------
        float
            value of objective function
        array of floats
            values of computed concentrations
        """
        # Modification of parameters in lpm
        self.lpm.set_param_from_array(param)
        # Concentration computed (this function without dataframe for performance issues)
        model_c = self.tracers.convolution(self.lpm,prepare=True,opt=True)
        # Squared difference
        #JRBUG
        if any(data_error==0):         
            print("error concentration errors not defined")
            print(data_error)
            print(self.lpm.name)
        #JRBUG
        diff = sum (objective_function(data_c,model_c,data_error))
        # diff = sum(np.square((model_c-data_c)/data_error))
        if conc==True : 
            return [diff,model_c]
        else: 
            return diff
    

    def display_concentrations(self):
        """ 
        Dislays concentration results 
        """
        self.lpm.display()
        self.cdata.display()
        concentration_computed = self.tracers.convolution(self.lpm,return_type="concentrations_set",prepare=False)
        concentration_computed.display()
        print("J=",self.cdata.sqrt_quadratic_mean_diff(concentration_computed))
  
        
    def display_lpms(self,display_options,lpm_results,lpm_reference=None):
        """ 
        Display lpm results
        
        Arguments
        ---------
        display_options: 
            Options for the display
        lpm_results: LPMDist
            All results of the calibration
        lpm_reference: LPM
            Target LPM (if existing, eg )
        """
        #JR: Should it be different
        if self.method == "Simplex" or self.method == "Simplex_init_multipes": 
            # Comparison of parameters
            if display_options.text and lpm_reference != None : 
                [exist,lpm]=lpm_results.get_best_lpm()
                if exist: lpm.display_parameters(lpm_reference)
        if self.method == "forward_uncertainty_quantification" or self.method == "Metropolis_Hastings" :
            # Distribution of parameters
            if display_options.figure : 
                lpm_results.display_parameters_dist(self_method=self.method,lpm_reference=lpm_reference,bins=100,directory=self.display_options.directory)


    def write_calibrated_lpm(self,lpm_results,file_prior="none",folder_prior=""): 
        """ 
        Writes the calibrated lpms
        """ 
        # Writes calibration parameters and efficiencty results
        self.write_parameters(os.path.join(self.display_options.directory,"parameters_calibration.txt"))
        self.write_results(os.path.join(self.display_options.directory,"results_calibration.txt"))
        # Writes distribution of "best" lpm
        if self.method != "Simplex" : 
            lpm_results.write_dist(os.path.join(self.display_options.directory,"lpm_dist_calibrated.txt"))
            lpm_results.write_histograms(os.path.join(self.display_options.directory,"lpm_histo_calibrated.txt"))
            lpm_results.write_stats(os.path.join(self.display_options.directory,"lpm_stats_calibrated.txt"))
            lpm_results.computes_and_writes_dist_params(os.path.join(self.display_options.directory,"lpm_param_dist_calibrated.txt"))
        if self.method == "Metropolis_Hastings" : 
            lpm_results.write_histograms(os.path.join(folder_prior_posterior(self.display_options.directory,stageup=-5,folder_prior=folder_prior),file_prior+".txt"))
        # Writes "best" lpm
        # [exist,lpm]=lpm_results.get_best_lpm()
        # if exist: lpm.write(os.path.join(self.display_options.directory,"lpm_calibrated.txt"),open_file=True)


    def write_results(self,file_name):
        """ 
        Writes parameters of calibration
        """
        data={}
        # Generic results for all calibration methods
        data['time_perform'] = self.time_perform
        # Specific results to this calibration method
        self.write_results_spec(data)
        # Writing in file
        file = open(file_name,"w")
        for key, val in data.items():
            file.write(key+'\t'+str(val)+'\n')
        file.close()
        
