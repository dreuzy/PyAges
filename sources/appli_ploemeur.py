# -*- coding: utf-8 -*-
"""
Created on Tue May 25 18:46:04 2021

@author: dreuzy
"""

import copy
import functools
import math
import numpy as np
import sys        
import os   
import time as time
import multiprocessing as mp        
import pandas as pd                          

import convolutions.concentrations as concentrations        # List of chemical concentrations
import global_parameters as gp
import convolutions.concentrations as co
import ploemeur.concentrations_time as ct

import calibration.calibration_exploration as calibration_exploration
import calibration.calibration_basis as calbas
import calibration.calibration_simplex as csimp
import calibration.calibration_Metropolis_Hastings as cMH

import ploemeur.appli_ploemeur_tools as appli_ploemeur_tools
import appli_ploemeur_results_comparison as aprc


# Proxy function for parallel simulation 
def perform(pod,i): 
    pod[i].perform()


class SimulationStrategy: 
    """
    Strategy of Simulation including parameterization and execution
    options : list of strings
        Type of simulation that should be performed     
        option == "all" : analysis of all years cumulatively between start and end
        option == "suc" : analysis of all years successively (independently)
        option == "span" : analysis of all years spanning the largest range of years and accounting for breakups 
    breakups : list of floats
        breakup years which "span" option should consider
    prior : list of bool
        As many as options     
    likelyhood : list of bool
        As many as options     
    errors : list of float
        List of errors that should be investigated
    well_select : list of strings
        List of wells on which the analysis should be performed
    folder : string
        root folder in which results should be stored
    """
    
    def __init__(self):
        # self.options =    ["span_prior","suc_prior","suc","all"]
        # self.prior  =     [True, True, False, False]
        # self.likelyhood = [True, True, True,  True]

        # self.options =    ["span_prior","suc_prior"]
        # self.errors=[0.3]#,0.15,0.25,0.05]
        # self.likelyhood = [True, True]
        # self.prior  =     [True, True]
        # self.prior_folder = ["span","span_prior"]
        # self.folder = "ploemeur_apriori_double_"

        self.errors=[0.2,0.3]#,0.15,0.25,0.05]

        # apriori_type = "none"
        apriori_type = "single"
        # apriori_type = "double"
        
        if apriori_type == "none" :
            self.options =    ["suc"]
            self.prior  =     [False]
            self.likelyhood = [True]
            self.prior_folder = [""]
            self.folder = "ploemeur_"
            
        if apriori_type == "single" :
            self.options =    ["span","suc_prior"]
            self.prior  =     [False, True]
            self.likelyhood = [True,  True]
            self.prior_folder = ["","span"]
            self.folder = "ploemeur_apriori_simple_"

        if apriori_type == "double" :
            self.options =    ["span","span_prior","suc_prior"]
            self.likelyhood = [True, True, True]
            self.prior  =     [False, True, True]
            self.prior_folder = ["","span","span_prior"]
            self.folder = "ploemeur_apriori_double_"
        
        # self.options =    ["suc","all"]
        # self.errors=[0.3]#,0.15,0.25,0.05]
        # self.prior  =     [False, False]
        # self.likelyhood = [True,  True]
        # self.prior_folder = ["",""]
        # self.folder = "ploemeur_"


        self.breakups=[2012]
        self.well_select = ["F34","PE","MF1","MF4","F38b","F11","F09","PZ2","PSR1"]
        self.parallel=False#JRJR
        self.explo_res=int(2000/10)#JRJR
        self.MH_nsteps=int(200000/100)#JRJR
        
        
    def test_F09(self): 
        self.options =    ["suc_prior"]
        self.prior  =     [True]
        self.likelyhood = [False]
        self.options =    ["span","suc_prior","suc","all"]
        self.prior  =     [False, True, False, False]
        self.likelyhood = [True,  False, True, True]
        self.breakups=[2012]
        self.folder = "ploemeur_apriori_test"
        self.errors=[0.05]
        self.well_select = ["F09"]
        self.MH_nsteps=200000
        self.parallel=False
        
        
    def execute(self): 
        """ 
        Execution over all combinations listed previously on 
            - errors
            - options
            - wells
        """
        for error in self.errors: 
            for option, prior, likelyhood, prior_folder in zip (self.options, self.prior, self.likelyhood, self.prior_folder): 
                # Gets the right combination of wells, dates, errors and lpm_types
                wells,datess,errors,lpm_types = selector(self.well_select,error=error)
                file_root=self.folder + str(error) + option
                
                # Loop on the wells
                for k in range(len(wells)):
                    self.__execute_parallel(wells[k], datess[k], lpm_types[k], \
                                            file_root, option, error, prior, likelyhood, prior_folder)


    def __execute_parallel(self, well, dates, lpm_types, file_root, option, error, prior, likelyhood, prior_folder):
        """
        Parallelizable Execution over all combibations of 
            - dates 
            - lpms 
        """
        
        # Creates and Returns list of files according to option "all" or "suc"
        files=files_years(well,dates,option,self.breakups)
        if option == "suc_prior" or option == "span_prior":
            prior_corresp=correspondance_matrix(well,dates,option,self.breakups)
        # New results folder for this well (with date and time)
        [dir_out,dir_root,date_file]=appli_ploemeur_tools.ploemeur_results_folder(file_root)
        
        # Preprocess
        # Loop on LPM models 
        pod_parallel=[]
        for lpm in lpm_types: 
            # Loop on the dates
            for well_date in files: 
                if option == "suc_prior" or option == "span_prior":
                    temp_file = calbas.file_prior_posterior(prior_corresp[well_date], error, lpm)
                    temp_folder = calbas.folder_prior_posterior(dir_out,stageup=-2,folder_prior=prior_folder)
                    prior_file = os.path.join(temp_folder,temp_file)
                else: 
                    prior_file = ""
                pod = ploemeur_one_date(dir_out,well_date,error,lpm,self.explo_res,self.MH_nsteps,prior,likelyhood,prior_file=prior_file,option=option)
                if self.parallel == True: 
                    pod_parallel.append(pod)
                else:
                    pod.perform()
        
        # Process
        st=time.time()
        if self.parallel == True: 
            # Perform parallel
            pool = mp.Pool(6)
            for i in range(len(pod_parallel)): 
                pool.apply_async(perform, args=(pod_parallel,i))
            pool.close()
            pool.join()
        print('time=',time.time()-st)
            
        # PostProcess: concatenation of results from the different dates and lpms
        for lpm in lpm_types: 
            aprc.load_and_display(date_file,lpm,dir_root)



def ploemeur_data_selection(well,dates,start,end):
    """ 
    Selection of concentrations by year
        + Stores selected data in another file     
        + Returns output file (same directory)
        
    Parameters
    ----------
    well: str
        well name, ef F09
    dates: str
        Min_Max years in the format: 2005_2020
    start, end: int
        Go by pairs 
        start: 2015
        end:   2018
    
    Returns
    -------
    file_out: str
        File name of the output file
        eg 'F09_2005_2005'

    """
    
    directory = appli_ploemeur_tools.ploemeur_data_folder()
    # Loads concentrations 
    cdata=appli_ploemeur_tools.ploemoeur_concentrations_ori(well,dates)
    df = cdata.cv
    # Selects concentrations within the given age range
    dfselec = df.loc[(df['date'] >= start) & (df['date'] <= (end+1))]
    # Writes data in a file 
    file_out = well + "_" + str(start) + "_" + str(int(max(dfselec['date']))) 
    dfselec.to_csv(os.path.join(directory,file_out),sep='\t', index = False)
    return file_out


def periods_years(well,dates,option,breakups=[]): 
    """
    Sampling years avialble for this well
    # years: array of int, List of years
    #        ex. [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
    """
    cdata=appli_ploemeur_tools.ploemoeur_concentrations_ori(well,dates)
    sampling_years=sorted(functools.reduce(lambda l, x: l.append(int(x)) or l if int(x) not in l else l, cdata.cv['date'], []))
    
    start=[];end=[]
    if option == "span" or option =="span_prior": 
        # start: [2005,2005,2012]
        # end:   [2020,2012,2020]
        if option == "span" : 
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
        for breakyear in breakups: 
            if breakyear > sampling_years[0] and breakyear < sampling_years[-1]: 
                start = start + [sampling_years[0],breakyear]
                end = end + [breakyear,sampling_years[-1]]    
        if len(start)==0:
            start.append(sampling_years[0])
            end.append(sampling_years[-1])
    else: 
        for i in range(len(sampling_years)-1):
            if option=="suc" or option=="suc_prior" :
                # start: [2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005]
                # end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
                start.append(sampling_years[i])  
                end.append(sampling_years[i+1])   
            elif(option=="all"): 
                # start: [2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005]
                # end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
                start.append(sampling_years[0])  
                end.append(sampling_years[i+1])
            else: 
                print("option not well defined ", option)

    return start,end,sampling_years



def files_years(well,dates,option,breakups=[]): 
    """
    Creates and Returns list of files according to option "all" or "suc"
    
    Parameters 
    ----------
    option: str
        option=="all": all years from start to end of dates
        option=="suc": one year independently of the other years
        option=="span": only the span of years between ending and intermediary years  
    breakups: list of int
        years of breakup at which hydrological regimes have changed (objectivally), eg. drastic changes of pumping rates
    
    Returns
    -------
    files: array of str
        List of corresponding file names, eg: 
        ['F09_2005_2005', 'F09_2005_2006', 'F09_2005_2007', 'F09_2005_2010', 'F09_2005_2013', 'F09_2005_2014', 'F09_2005_2015', 'F09_2005_2016', 'F09_2005_2017', 'F09_2005_2018', 'F09_2005_2019']
        
    """

    start,end=periods_years(well,dates,option,breakups)[0:2]

    # Corresponding file names for each pair of years
    # all: ['F09_2005_2005', 'F09_2005_2006', 'F09_2005_2007', 'F09_2005_2010', 'F09_2005_2013', 'F09_2005_2014', 'F09_2005_2015', 'F09_2005_2016', 'F09_2005_2017', 'F09_2005_2018', 'F09_2005_2019']
    # suc: ['F09_2005_2005', 'F09_2006_2006', 'F09_2007_2007', 'F09_2010_2010', 'F09_2013_2013', 'F09_2014_2014', 'F09_2015_2015', 'F09_2016_2016', 'F09_2017_2017', 'F09_2018_2018', 'F09_2019_2019']
    files=[]
    for k in range(len(start)):
        files.append(ploemeur_data_selection(well,dates,start[k],end[k]))
    return files


def correspondance_matrix(well,dates,option,breakups=[]): 
    """
    Correspondance matrix between
        - single years
        - multiple years that should give the a priori for the single years
    Assumes that breakups is of size 1 and only 1!!!
    Returns
    -------
    dataframe such as :         
            file_current     file_prior
        0  F09_2005_2005  F09_2005_2010
        0  F09_2006_2006  F09_2005_2010
        0  F09_2007_2007  F09_2005_2010
        0  F09_2010_2010  F09_2005_2010
        0  F09_2013_2013  F09_2012_2020
        0  F09_2014_2014  F09_2012_2020
        0  F09_2015_2015  F09_2012_2020
        0  F09_2016_2016  F09_2012_2020
        0  F09_2017_2017  F09_2012_2020
        0  F09_2018_2018  F09_2012_2020
        0  F09_2019_2019  F09_2012_2020
        0  F09_2020_2020  F09_2012_2020
    """
    # Successive years start, end and files
    if option == "span_prior": 
        start_suc,end_suc,sampling_years_suc=periods_years(well,dates,"span_prior",breakups)
        files_suc = files_years(well,dates,"span_prior",breakups)
    else : 
        start_suc,end_suc,sampling_years_suc=periods_years(well,dates,"suc",breakups)
        files_suc = files_years(well,dates,"suc",breakups)
    # Prior year span start, end and files
    start_prior,end_prior,sampling_years_prior=periods_years(well,dates,"span",breakups)
    files_prior = files_years(well,dates,"span",breakups)
    # df: correspondance matrix 
    dic = {}
    for file, start, end in zip (files_suc, start_suc, end_suc):
        if option == "span_prior": 
            temp = files_prior[0]
        elif option == "suc_prior": 
            if len(files_prior) != 3: 
                temp=files_prior[0]
            else: 
                if start < breakups[0] : 
                    temp = files_prior[1]
                else : 
                    temp = files_prior[2]
        dic[file]=temp
        
    return dic

        
class ploemeur_one_date:
    """ 
    ELEMENTARY interpretation of concentrations for
        - one well    
        - one range of date
        - one error value 
        - one lpm type
    
    Attributes, public
    -------------------
        directory_ploemeur: str
            directory of Ploemeur data
        file_ploemeur: str
            File of Ploemeur data
        error_concentrations: float
            Level of concentration erros (as percentage)
        LPM_type: str
            Type of LPM that should be used
        directory_lpm: str 
            Directory of LPM data  
        display: instance of display_options class
            All display parameters (and there is a number of them!)
    
    Attributes, private
    -------------------
        calstrat_MH: CalibrationMetropolisHastings
            Instance of calibration class, contains the parameters of the calibration method
        calstrat_FUQ: CalibrationMetropolisHastings
            Instance of calibration class, contains the parameters of the calibration method

    """
    def __init__(self,directory_results,well_date,error_concentrations,lpm_type,explo_res,MH_nsteps,prior,likelyhood,prior_file="",option=""):
        """ 
        """
        self.option=option
        # ---------------- CONCENTRATIONS DATA ------------------
        # Concentration data 
        self.directory_ploemeur = appli_ploemeur_tools.ploemeur_data_folder()
        self.file_ploemeur = well_date 
        self.error_concentrations = error_concentrations

        # ---------------- LPM MODEL -----------------------------
        self.lpm_type = lpm_type
        self.directory_lpm = os.path.join(self.directory_ploemeur,"LPM_data")

        # ---------------- METROPOLIS HASTINGS --------------------
        # Method and Parameters  
        self.calstrat_MH = cMH.CalibrationMetropolisHastings(nstep=MH_nsteps,prior_option=prior,likelyhood=likelyhood,
                                                             monitor=True,display_traj=True,prior_typ="empirical",prior_file=prior_file) # JR: 250000
        # self.calstrat[1].MH_step.define_by_prop(0.005)
        self.calstrat_MH.MH_step.define_by_value()
        # self.calstrat_MH.set_nmodels(explo_res)

        
        # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
        self.calstrat_FUQ = csimp.CalibrationSimplex("forward_uncertainty_quantification",
                                                    init_multiples_n=2,fuq_n=2) #JR: 5,50
        
                
        # ---------------- CALIBRATION ANALYSIS --------------------
        self.__nmodels = explo_res
        
        # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
        # Output options
        self.display = gp.display_options()
        self.display.text = True
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True    
        self.display.directory = gp.results_directory(gp.results_directory(directory_results,well_date),lpm_type)
        self.display_reachconc = False

    def concentration_preparation(self): 
        """
        Concentrations 
        - Loading
        - Error affectation (relative error)
        - Display
        - Write to root results directory
        """
        # Data Loading
        cdata=co.Concentrations(file_load=True, file_name=os.path.join(self.directory_ploemeur,self.file_ploemeur))
        # Adds some percentage of uncertainty to the data
        if min(cdata.cv.iloc[:,gp.ERROR])==0: 
            cdata.error_affect_from_value(self.error_concentrations)
        cdata.display(self.display)
        # Copy results to root directory
        cdata.cv.to_csv(os.path.join(self.display.directory,"concentrations.txt"),sep='\t') 
        return cdata
    
    
    def calibration(self,cdata,calstrat): 
        """
        calibration with the method calstrat (either MH or FUQ)
        """
        # display_options to be used for this case with specific directory  (no change in generic display_options)
        display_options_case = copy.deepcopy(self.display)
        display_options_case.directory = gp.results_directory(self.display.directory,calstrat.method)
        # Calibration preparation and analysis
        # calstrat.set_nmodels(10)
        calib_basis=calbas.CalibrationBasis(cdata,self.lpm_type,display_options=display_options_case,nmodels=self.__nmodels,reachconc=self.display_reachconc)
        calstrat.update_calibbasis(calib_basis)
        # Calibration performs
        lpm_results=calstrat.perform()
        # Stores/Writes Results
        calstrat.write_calibrated_lpm(lpm_results,file_prior=calbas.file_prior_posterior(self.file_ploemeur,self.error_concentrations,self.lpm_type),folder_prior=self.option)
        # Calibration analysis
        calstrat.analysis_calibration(lpm_results)
        # Chronicles of tracers with data 
        ct.display_concentration_chronicles(cdata,lpm_results,calstrat.method,self.display)
        # Distribution of parameters and concentrations
        if self.display_reachconc == True : 
            lpm_results.display_parameters_dist(self_method=calstrat.method,directory=display_options_case.directory)
        if calstrat.method == "Metropolis_Hastings" and calstrat.prior.option == True: 
            lpm_results.display_parameters_dist_comp_apriori(directory=display_options_case.directory,prior=calstrat.prior)
        if self.display_reachconc == True : 
            lpm_results.display_concentrations_dist(self_method=calstrat.method,concentrations_reference=cdata,directory=display_options_case.directory)
        
        return lpm_results
        
        

    def perform(self): 
        """ 
        peforms interpretation with Metropolis Hastings
        """
        # ---------------- CONCENTRATIONS------------------------
        cdata = self.concentration_preparation()
        # ---------------- CALIBRATION with MH -----------------
        self.calibration(cdata,self.calstrat_MH)


    def perform_method_comparison(self): 
        """ 
        peforms interpretation 
        """
        
        # ---------------- CONCENTRATIONS------------------------
        cdata = self.concentration_preparation()
        
        # ---------------- CALIBRATION --------------------------
        lpm_results=[None]*2
        lpm_results[0]=self.calibration(cdata,self.calstrat_MH)
        lpm_results[1]=self.calibration(cdata,self.calstrat_FUQ)
        
        # ---------------- SYNTHETIC FIGURES --------------------
        lpm_results[0].display_parameters_dist(self_method=self.calstrat_MH.method,lpm_reference=None,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat_FUQ.method,directory=self.display.directory)
        lpm_results[0].display_concentrations_dist(self_method=self.calstrat_MH.method,concentrations_reference=cdata,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat_FUQ.method,directory=self.display.directory)
        

# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------

def selector(well_select,error=0.03): 
    # Selection of wells, dates, errors and models
        
    # Adds wells 
    wells=[];datess=[]; errors=[]; lpm_types=[]
    # wells.append("F38")
    # datess.append("2004_2020")
    # errors.append(0.03)
    # wells.append("F13")
    # datess.append("2005_2020")
    # errors.append(0.03)
    # wells.append("F22")
    # datess.append("2004_2016")
    # errors.append(0.03)
    # wells.append("F28")
    # datess.append("2005_2020")
    # errors.append(0.03)
    # wells.append("MF1")
    # datess.append("2004_2020")
    # errors.append(0.03)
    # wells.append("F11")
    # datess.append("2004_2021")
    # errors.append(0.03)
    # wells.append("F09")
    # datess.append("2005_2021")
    # errors.append(0.03)
    # wells.append("PE")
    # datess.append("2005_2020")
    # errors.append(0.03)
    
    if "F09" in well_select : 
        wells.append("F09")
        datess.append("2005_2024")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_old","exp_shifted_young","exp_shifted"])
        # lpm_types.append(["exp_shifted","exp_shifted_young","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])    
        
    if "F34" in well_select : 
        wells.append("F34")
        datess.append("2004_2015")
        errors.append(error)
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
       
    if "F11" in well_select : 
        wells.append("F11")
        datess.append("2004_2024")
        errors.append(error)
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "F38" in well_select : 
        wells.append("F38")
        datess.append("2006_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])

    if "F38b" in well_select : 
        wells.append("F38b")
        datess.append("2006_2011")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
                
    if "MF4" in well_select : 
        wells.append("MF4")
        datess.append("2006_2017")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "PE" in well_select : 
        wells.append("PE")
        datess.append("2005_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "MF1" in well_select : 
        wells.append("MF1")
        datess.append("2004_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted_young","exp_shifted","exp_shifted_old"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])

    if "PZ2" in well_select : 
        wells.append("PZ2")
        datess.append("2009_2024")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])

    if "PSR1" in well_select : 
        wells.append("PSR1")
        datess.append("2009_2024")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","exp_shifted_old","exp_shifted_young","ig_shifted","ig","dirac_double_1_set","gamma","uniform","exp"])
        # lpm_types.append(["exp_shifted"])
        lpm_types.append(["gamma","uniform","exp_shifted","ig_shifted","ig","dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])

        
    return wells,datess,errors,lpm_types
    
    
    
if __name__ == "__main__":  
    
    # Initialization 
    simulstart=SimulationStrategy()
    
    # Type of simlation 
    # simulstart.test_F09()
    
    # Execution of simulation
    simulstart.execute()
    
    
    
    
# # Step 1: Redefine, to accept `i`, the iteration number
# def howmany_within_range2(row, minimum, maximum):
#     """Returns how many numbers lie within `maximum` and `minimum` in a given `row`"""
#     count = 0
#     for n in row:
#         print(os.getpid(),n,row)
#         if minimum <= n <= maximum:
#             count = count + 1
#     time.sleep(1)
    
        # # Prepare data
        # np.random.RandomState(100)
        # arr = np.random.randint(0, 10, size=[6, 3])
        # data = arr.tolist()
        # data[:5]
        # print(data)

        # pool = mp.Pool(2)
        
        # # Step 3: Use loop to parallelize
        # for row in data:
        #     pool.apply_async(howmany_within_range2, args=(row, 4, 8))
    
    
        # # Step 4: Close Pool and let all the processes complete    
        # pool.close()
        # pool.join()  # postpones the execution of next line of code until all processes in the queue are done.


    
    
    
    
    






