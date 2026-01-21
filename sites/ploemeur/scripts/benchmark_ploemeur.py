import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
for p in (repo_root, repo_root / "sources"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# -*- coding: utf-8 -*-
"""
Created on Tue May 18 21:10:20 2021

@author: Jean-Raynald de Dreuzy
    """

import copy
import sys
import os
import math

import convolutions.concentrations as co
from convolutions import concentrations_time as ct
import convolutions.concentrations as concentrations
import global_parameters as gp
import LPM.LPM_generate as LPM_generate

import calibration.calibration_exploration as calibration_exploration
import calibration.calibration_basis as calbas
import calibration.calibration_simplex as csimp
import calibration.calibration_Metropolis_Hastings as cMH

from sites.ploemeur.postprocessing import appli_ploemeur_tools


def benchmark_ploemeur():
    # ---------------- CONCENTRATIONS DATA ------------------
    # Concentration data
    # file = "ploemeur_F22_2007"
    # date = 2007
    file = "ploemeur_F09_2010"
    date = 2010
    verbose = True
    
    # ---------------- LPM MODEL -----------------------------
    lpm_type = "dirac_double"
    directory_lpm = os.path.join(gp.DIRECTORY_TEST,"ploemeur","LPM_data")
    # Resolution of objective function / concentration pattern
    resolution = 2000
    
    # ---------------- OUTPUT DIRECTORY ----------------------
    directory_results = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,"test_cases")
    directory_results = gp.results_directory(directory_results,file)
    
    # ---------------- CALIBRATION PARAMETERS ----------------
    calstrat=[None]*2
    
    # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
    calstrat[0] = csimp.CalibrationSimplex("forward_uncertainty_quantification",
                                                init_multiples_n=1*2,fuq_n=1*5) #JR: 5,50
    
    # ---------------- METROPOLIS HASTINGS --------------------
    # Method and Parameters  
    calstrat[1] = cMH.CalibrationMetropolisHastings(nstep=2500,prior=False,likelyhood=True, lpm_number=10,
                                                         monitor=True,display_traj=True) # JR: 250000
    # calstrat[1].MH_step.define_by_prop(0.005)
    calstrat[1].MH_step.define_by_value()
    
    # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
    # Output options
    display = gp.display_options()
    display.text = True
    display.figure = True
    display.figure_close = False#JR True
    display.figure_save = True
    display.directory = directory_results
    
    #---------------------------------------------------------
    # ---------------- CONCENTRATIONS-------------------------
    # Data Loading
    
    filename=os.path.join(gp.DIRECTORY_TEST,"ploemeur",file)
    if verbose:
        print("Data file location: ", filename)
    concentration_sampled=co.Concentrations(file_load=True, file_name = filename)
    # Adds some percentage of uncertainty to the data
    # concentration_sampled.error_affect_from_value(error_concentrations)
    concentration_sampled.display(display)
    # Copy results to root directory
    concentration_sampled.cv.to_csv(os.path.join(display.directory,"concentrations.txt"),sep='\t')
    
   
    # ---------------- CALIBRATION -------------
    lpm_results=[None]*2
    for i in range(len(calstrat)):
        # Outputs of Interpration
        display_calstrat=copy.deepcopy(display)
        display_calstrat.directory = gp.results_directory(display.directory,calstrat[i].method)
        # Calibration
        calib_basis=calbas.CalibrationBasis(concentration_sampled,lpm_type,display_options=display_calstrat,directory_lpm=directory_lpm)
        calstrat[i].update_calibbasis(calib_basis)
        lpm_results[i]=calstrat[i].perform()
        # Stores/Writes Results
        calstrat[i].write_calibrated_lpm(lpm_results[i])
        
        
    # ---------------- Analysis of Calibration Problem (reachable concentrations and objective function)
    calstrat[1].analysis_calibration()

    
    # ---------------- SYNTHETIC FIGURES --------------------
    lpm_results[0].display_parameters_dist(self_method=calstrat[0].method,lpm_reference=None,
                                                   lpm_2nd=lpm_results[1],
                                                   lpm_2nd_method=calstrat[1].method,
                                                   directory=display.directory)
    lpm_results[0].display_concentrations_dist(self_method=calstrat[0].method,
                                                       concentrations_reference=concentration_sampled,
                                                       lpm_2nd=lpm_results[1],
                                                       lpm_2nd_method=calstrat[1].method,
                                                       directory=display.directory)
    

    # ------------- CONCENTRATION OUTPUTS ----------------------
    lpm=LPM_generate.LPM_generate(lpm_type,directory_lpm=gp.directory_lpm_data)
    ct.display_concentration_times([display.directory],lpm,display)


if __name__ == "__main__":
    benchmark_ploemeur()
