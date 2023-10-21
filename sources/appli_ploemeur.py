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
    dfselec = df.loc[(df['date'] >= start) & (df['date'] <= end)]
    # Writes data in a file 
    file_out = well + "_" + str(start) + "_" + str(int(max(dfselec['date']))) 
    dfselec.to_csv(os.path.join(directory,file_out),sep='\t', index = False)
    return file_out


def ploemeur_data_years(well,dates): 
    """ 
    Returns list of years of the data 
    
    Parameters
    ----------
    well: str
        well name
    dates: str
        Min_Max years in the format: 2005_2020
        
    Returns
    -------
    years: array of int
        List of years of the data, eg: 
            [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
        
    """
    cdata=appli_ploemeur_tools.ploemoeur_concentrations_ori(well,dates)
    date=cdata.cv['date']
    return sorted(functools.reduce(lambda l, x: l.append(int(x)) or l if int(x) not in l else l, date, []))

    
def successive_years(date):
    """ 
    Gets successive year intervals from the date
    
    Parameters
    ----------
    date: array of int
        List of years
        [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
        
    Returns
    -------
    start, end: arrays of int
        Go by pairs start[i],end[i], eg: 
        start: [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019]
        end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
        
    """
    start=[];end=[]
    for i in range(len(date)-1):
        start.append(date[i])  
        end.append(date[i+1])   
    return start,end


def all_years_from_start(date):
    """ 
    Gets all year intervals from the first year
    
    Parameters
    ----------
    date: array of int
        List of years
        [2005, 2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
        
    Returns
    -------
    start, end: arrays of int
        Go by pairs start[i],end[i], eg: 
        start: [2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005, 2005]
        end:   [2006, 2007, 2010, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020]
        
    """
    start=[];end=[]
    for i in range(len(date)-1):
        start.append(date[0])  
        end.append(date[i+1])   
    return start,end


def files_years(well,dates,option): 
    """
    Creates and Returns list of files according to option "all" or "suc"
    
    Parameters 
    ----------
    option: str
        option=="all": all years from start to end of dates
        option=="suc": one year independently of the other years
    
    Returns
    -------
    files: array of str
        List of corresponding file names, eg: 
        ['F09_2005_2005', 'F09_2005_2006', 'F09_2005_2007', 'F09_2005_2010', 'F09_2005_2013', 'F09_2005_2014', 'F09_2005_2015', 'F09_2005_2016', 'F09_2005_2017', 'F09_2005_2018', 'F09_2005_2019']
        
    """
    
    # Sampling years avialble for this well
    years=ploemeur_data_years(well,dates)
    if(option=="suc"):
        [start,end]=successive_years(years)
    else: 
        [start,end]=all_years_from_start(years)
    # Corresponding file names for each pair of years
    files=[]
    for k in range(len(start)):
        files.append(ploemeur_data_selection(well,dates,start[k],end[k]))
    return files


        
class ploemeur_one_date:
    """ 
    Interpretation of concentrations at one date on ploemeur site
    """
    def __init__(self,directory_results,well_date="F11_2010",error_concentrations=0.06,lpm_type="ig"):
        """ 
        """
        # ---------------- CONCENTRATIONS DATA ------------------
        # Concentration data 
        self.directory_ploemeur = appli_ploemeur_tools.ploemeur_data_folder()
        self.file_ploemeur = well_date 
        self.error_concentrations = error_concentrations

        # ---------------- LPM MODEL -----------------------------
        self.lpm_type = lpm_type
        self.directory_lpm = os.path.join(self.directory_ploemeur,"LPM_data")
        # Resolution of objective function / concentration pattern
        self.resolution = 200  # 2000
        
        self.calstrat=[None]*2
        # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
        self.calstrat[1] = csimp.CalibrationSimplex("forward_uncertainty_quantification",
                                                    init_multiples_n=2,fuq_n=2) #JR: 5,50
        
        # ---------------- METROPOLIS HASTINGS --------------------
        # Method and Parameters  
        self.calstrat[0] = cMH.CalibrationMetropolisHastings(nstep=10000,prior=False,likelyhood=True,
                                                             monitor=True,display_traj=True) # JR: 250000
        # self.calstrat[1].MH_step.define_by_prop(0.005)
        self.calstrat[0].MH_step.define_by_value()
                
        # ---------------- CALIBRATION ANALYSIS --------------------
        self.__nmodels = 500 # 10000
        
        # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
        # Output options
        self.display = gp.display_options()
        self.display.text = True
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True    
        directory_results = gp.results_directory(directory_results,well_date)
        self.display.directory = gp.results_directory(directory_results,lpm_type)


    def perform(self): 
        """ peforms interpration 
        """
        
        # ---------------- CONCENTRATIONS------------------------
        # Data Loading
        cdata=co.Concentrations(file_load=True, file_name=os.path.join(self.directory_ploemeur,self.file_ploemeur))
        # Adds some percentage of uncertainty to the data
        if min(cdata.cv.iloc[:,gp.ERROR])==0: 
            cdata.error_affect_from_value(self.error_concentrations)
        cdata.display(self.display)
        # Copy results to root directory
        cdata.cv.to_csv(os.path.join(self.display.directory,"concentrations.txt"),sep='\t') 
        
        # ---------------- CALIBRATION --------------------------
        lpm_results=[None]*2
        for i in range(len(self.calstrat)):
            # display_options to be used for this case with specific directory  (no change in generic display_options)
            display_options_case = copy.deepcopy(self.display)
            display_options_case.directory = gp.results_directory(self.display.directory,self.calstrat[i].method)
            # Calibration preparation and analysis
            calib_basis=calbas.CalibrationBasis(cdata,self.lpm_type,display_options=display_options_case,nmodels=self.__nmodels)
            self.calstrat[i].update_calibbasis(calib_basis)
            # Calibration performs
            lpm_results[i]=self.calstrat[i].perform()
            # Stores/Writes Results
            self.calstrat[i].write_calibrated_lpm(lpm_results[i])
            # Calibration analysis
            self.calstrat[i].analysis_calibration(lpm_results[i])
            # Chronicles of tracers with data 
            ct.display_concentration_chronicles(cdata,lpm_results[i],self.calstrat[i].method,self.display)
            # Distribution of parameters and concentrations
            lpm_results[i].display_parameters_dist(self_method=self.calstrat[i].method,directory=display_options_case.directory)
            lpm_results[i].display_concentrations_dist(self_method=self.calstrat[i].method,concentrations_reference=cdata,directory=display_options_case.directory)
        
        # ---------------- SYNTHETIC FIGURES --------------------
        lpm_results[0].display_parameters_dist(self_method=self.calstrat[0].method,lpm_reference=None,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat[1].method,directory=self.display.directory)
        lpm_results[0].display_concentrations_dist(self_method=self.calstrat[0].method,concentrations_reference=cdata,lpm_2nd=lpm_results[1],lpm_2nd_method=self.calstrat[1].method,directory=self.display.directory)
        

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
    
        
    if "F34" in well_select : 
        wells.append("F34")
        datess.append("2004_2015")
        errors.append(error)
        lpm_types.append(["exp_shifted"])#,"ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
       
    if "F11" in well_select : 
        wells.append("F11")
        datess.append("2004_2021")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "F38" in well_select : 
        wells.append("F38")
        datess.append("2006_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])

    if "F38b" in well_select : 
        wells.append("F38b")
        datess.append("2006_2011")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "F09" in well_select : 
        wells.append("F09")
        datess.append("2005_2021")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted_old","exp_shifted_young","exp_shifted"])
        # lpm_types.append(["exp_shifted","exp_shifted_young","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "MF4" in well_select : 
        wells.append("MF4")
        datess.append("2006_2017")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "PE" in well_select : 
        wells.append("PE")
        datess.append("2005_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    if "MF1" in well_select : 
        wells.append("MF1")
        datess.append("2004_2020")
        errors.append(error)
        # lpm_types.append(["dirac_double_1_set"])
        # lpm_types.append(["exp_shifted","ig_shifted"])
        lpm_types.append(["exp_shifted","ig_shifted","dirac_double_1_set"])#,"gamma","uniform"])
        
    return wells,datess,errors,lpm_types


def perform(pod,i): 
    pod[i].perform()
    
    

def appli_ploemeur(well_select, file_root_root="ploemeur_", option="all", error=0.15):
    # Main analysis option 
    parallel=False
    
    wells,datess,errors,lpm_types = selector(well_select,error=error)
    file_root=file_root_root+str(error)+option
    
    # Loop on the wells
    for k in range(len(wells)):
        # Creates and Returns list of files according to option "all" or "suc"
        files=files_years(wells[k],datess[k],option)
        # New results folder for this well (with date and time)
        [dir_out,dir_root,date_file]=appli_ploemeur_tools.ploemeur_results_folder(file_root)
        
        # Preprocess
        # Loop on LPM models 
        pod=[]
        for lpm in lpm_types[k]: 
            # Loop on the dates
            for fn in files: 
                pod.append(ploemeur_one_date(dir_out,well_date=fn,error_concentrations=errors[k],lpm_type=lpm))
        
        # Process
        if parallel == True: 
            # Perform parallel
            st=time.time()
            pool = mp.Pool(14)
            for i in range(len(pod)): 
                pool.apply_async(perform, args=(pod,i))
            pool.close()
            pool.join()
            print('time parallel=',time.time()-st)
        else: 
            # Perform sequential
            st=time.time()
            for i in range(len(pod)): 
                pod[i].perform()
            print('time sequential=',time.time()-st)
            
        # PostProcess
        for lpm in lpm_types[k]: 
            aprc.load_and_display(date_file,lpm,dir_root)
    
    
if __name__ == "__main__":  
    
    # well_select = ["F09"]
    # appli_ploemeur(well_select, file_root_root="ploemeur_10_10_", option="suc", error=0.15)
    # appli_ploemeur(well_select, file_root_root="ploemeur_10_10_", option="all", error=0.15)
    
    # sys.exit()
    
    # well_select = ["F34","PE","MF1","MF4","F38b","F11","F09"]
    # well_select = ["F09","F11","F34","PE","MF1","MF4","F38b"]
    well_select = ["F09"]
    folder = "ploemeur_10_13_"
    # errors=[0.15,0.2,0.25,0.3]
    errors=[0.15]
    for error in errors: 
        appli_ploemeur(well_select, file_root_root=folder, option="suc", error=error)
        appli_ploemeur(well_select, file_root_root=folder, option="all", error=error)
    
    
    
    
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


    
    
    
    
    






