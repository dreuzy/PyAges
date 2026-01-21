# -*- coding: utf-8 -*-
"""
Created on Tue May 18 21:10:20 2021

@author: Jean-Raynald de Dreuzy
"""

import copy
import functools
import numpy as np
import sys
import os
import math

from convolutions import concentrations_time as ct
import convolutions.convolution_tracers as convolution_tracers                     # Chemical elements list
import convolutions.concentrations as concentrations        # List of chemical concentrations
import global_parameters as gp
import LPM.LPM_generate as LPM_generate
import convolutions.concentrations as co

import calibration.calibration_exploration
import calibration.calibration_basis as calbas
import calibration.calibration_simplex as csimp
import calibration.calibration_Metropolis_Hastings as cMH
import calibration.calibration_exploration
from sites.ploemeur.postprocessing import appli_ploemeur_tools


def benchmark_fontainebleau(): 
    # ---------------- CONCENTRATIONS DATA ------------------
    # Concentration data
    # file = "ploemeur_F22_2007"
    # date = 2007
    file = "fontainebleau_CGEB"
    
    # ---------------- LPM MODEL -----------------------------
    lpm_type = "mix_exp_shifted"#"exp_shifted"#"ig_shifted"#"dirac_double"
    directory_lpm = os.path.join(gp.ROOT_DIRECTORY, "sites", "fontainebleau", "data", "LPM_data")
    # Resolution of objective function / concentration pattern
    resolution = 2000
    
    # ---------------- OUTPUT DIRECTORY ----------------------
    directory_results = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,"test_cases")
    directory_results = gp.results_directory(directory_results,file)
    
    # ---------------- CALIBRATION PARAMETERS ----------------
    calstrat=[None]*2
    
    # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
    calstrat[0] = csimp.CalibrationSimplex("forward_uncertainty_quantification",
                                                init_multiples_n=1*5,fuq_n=1*10)
    
    # ---------------- METROPOLIS HASTINGS --------------------
    # Method and Parameters
    calstrat[1] = cMH.CalibrationMetropolisHastings(nstep=5000,prior=False,likelyhood=True,
                                                         monitor=True,display_traj=True) # JR: 250000
    # calstrat[1].MH_step.define_by_prop(0.005)
    calstrat[1].MH_step.define_by_value()
    
    # ---- DISPLAY OPTIONS + ROOT OUTPUT DIRECTORY ------------
    # Output options
    display = gp.display_options()
    display.text = True
    display.figure = True
    display.figure_close = True
    display.figure_save = True
    display.directory = directory_results
    
    # ---------------- CONCENTRATIONS------------------------
    # Data Loading
    concentration_sampled=co.Concentrations(file_load=True, file_name=os.path.join(gp.ROOT_DIRECTORY, "sites", "fontainebleau", "data", file))
    # Adds some percentage of uncertainty to the data
    # concentration_sampled.error_affect_from_value(error_concentrations)
    concentration_sampled.display(display)
    # Copy results to root directory
    concentration_sampled.cv.to_csv(os.path.join(display.directory,"concentrations.txt"),sep='\t')
    
    # ---------------- REACHABLE CONCENTRATIONS -------------
    print('Direct problem method: exploring reachable concentrations with a LPM model')
    directory_cr = gp.results_directory(display.directory,"reachable_concentrations")
    display_cr=copy.deepcopy(display)
    display_cr.directory_results=gp.results_directory(display.directory,"reachable_concentrations")
    
    cr = calibration_exploration.CalibrationExploration(lpm_type, concentration_sampled.names(),
                                                      date = concentration_sampled.cv["date"],
                                                      nmodels=resolution, display_options=display_cr)
    cr.compute_concentrations()
    cr.output()
    cr.display_with_data(concentration_sampled)
    
    # ---------------- CALIBRATION -------------
    print('Inverse problem method: calibrating a LPM model with data')
    lpm_results=[None]*2
    for i in range(len(calstrat)):
        # Outputs of Interpration
        directory_calibration = gp.results_directory(display.directory,calstrat[i].method)
        # Calibration
        calib_basis=calbas.CalibrationBasis(concentration_sampled,lpm_type,directory_results=directory_calibration,directory_lpm=directory_lpm)
        calstrat[i].update_calibbasis(calib_basis)
        lpm_results[i]=calstrat[i].perform()
        # Stores/Writes Results
        calstrat[i].write_calibrated_lpm(lpm_results[i])
    
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
    
    # ------- OBJECTIVE FUNCTION -------------------------------
    calstrat[1].build_objective_function(display,resolution=resolution)
    
    # ------------- CONCENTRATION OUTPUTS ----------------------
    lpm=LPM_generate.LPM_generate(lpm_type,directory_lpm=None)
    ct.display_concentration_times([display.directory],lpm,display)

if __name__ == "__main__":
    benchmark_fontainebleau()
