# -*- coding: utf-8 -*-
"""
Created on Tue May 18 21:10:20 2021

@author: Jean-Raynald de Dreuzy
"""

import os
import time

import global_parameters as gp

import calibration.workflows.synthetic_test as cst
import calibration.methods.simplex as csimp
import calibration.methods.metropolis_hastings as cMH


class comparison_MH_fuq:
    """ 
    Series of tested parameters 
    """
    def __init__(self):
        self.models_calib = ['ig','dirac','exp','exp_shifted','ig_shifted','dirac_double','gamma','uniform']
        self.display = gp.display_options()
        self.display.text = False
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True  
        self.fuq_n = 5 #50
        self.init_multiples_n = 1 #5
        self.MH_n = 2500
        directory = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,"test_calib_comp")
        self.directory_root = gp.results_directory(directory,gp.name_dhms()) 


    def perform(self, stime, ncase=3, error=0.04, tracer_names=["kr85","Li"], lpm_random=True, lpm_target=None,resolution=1000): 
        """ 
        Checks tracers and lpms
        """
        stime.initialize(len(self.models_calib))
        # OUTPUT File and Directory
        self.display.directory = gp.results_directory(self.directory_root,"prec_"+str(error))
        name = ""
        for t in tracer_names : name = name + "_" + t
        self.display.directory = gp.results_directory(self.display.directory,name) 
        date = 2010
        
        print('\\COMPARISON: FORWARD UNCERTAINTY QUANTIFICATION AND METROPOLIS HASTINGS')
        for lpm in self.models_calib:
            
            calstrat=[None]*2
            # ---------------- FORWARD UNCERTAINTY QUANTIFICATION -----------------------------
            calib_simplex = csimp.Simplex("forward_uncertainty_quantification",
                                                        init_multiples_n=self.init_multiples_n,fuq_n=self.fuq_n) 
            calstrat[0] = cst.CalibrationSyntheticTest(calib_strategy=calib_simplex,ncase=ncase,error=error,nmodels=resolution,
                                                       tracer_names=tracer_names,date=date,lpm_type=lpm,display_options=self.display)

            # ---------------- METROPOLIS HASTINGS --------------------
            # Method and Parameters  
            calib_MH = cMH.MetropolisHastings(nstep=self.MH_n,prior=False,likelyhood=True,
                                                                 monitor=True,display_traj=True) # JR: 250000
            calib_MH.MH_step.define_by_value() 
            # calib_MH.MH_step.define_by_prop(0.005)
            calstrat[1] = cst.CalibrationSyntheticTest(calib_strategy=calib_MH,ncase=ncase,error=error,
                                                       tracer_names=tracer_names,date=date,lpm_type=lpm,
                                                       nmodels=resolution,
                                                       display_options=self.display)
            
            # Loop on the ncases cases
            for i in range(ncase):
                start = time.time()
                lpm_calibration=[None]*2
                lpm_results=[None]*2
                # Performs calibration
                for j in range(len(calstrat)):
                    [lpm_target,lpm_calibration[j],concentration_sampled,lpm_results[j],_] = calstrat[j].perform_one_case(i,lpm_random=lpm_random,lpm_target=lpm_target)
                # Outputs and Displays results
                directory_common = gp.results_directory(self.display.directory,lpm)
                directory_common = gp.results_directory(directory_common,str(i))
                lpm_results[0].display_parameters_dist(self_method=lpm_calibration[0].method,
                                                               lpm_reference=lpm_target,lpm_2nd=lpm_results[1],
                                                               lpm_2nd_method=lpm_calibration[1].method,
                                                               directory=directory_common)
                lpm_results[0].display_concentrations_dist(self_method=lpm_calibration[0].method,
                                                                   concentrations_reference=concentration_sampled,
                                                                   lpm_2nd=lpm_results[1],
                                                                   lpm_2nd_method=lpm_calibration[1].method,
                                                                   directory=directory_common)
                # Analysis of calibration problem
                lpm_calibration[1].analysis_calibration()
                end = time.time()
                
            # Writes agregated parameters and results
            for i in range(len(lpm_calibration)):
                lpm_calibration[i].write_parameters(os.path.join(calstrat[i].get_directory(),"parameters_calibration.txt"))
                lpm_calibration[i].write_results(os.path.join(calstrat[i].get_directory(),"results_calibration.txt"))
                calstrat[i].write_parameters_test()
                calstrat[i].write_results()
            # Actualization of simulation time 
            stime.actualize()
        
        return [lpm_target,lpm_results,concentration_sampled,lpm_calibration]
  
    
# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------

def test_calibration_MH_fuq(): 
    comp = comparison_MH_fuq()
    stime = gp.simulation_time(nsim=6)
    comp.perform(stime, ncase=2, error=0.04, tracer_names=["cfc11","kr85"],resolution=10000)
    comp.perform(stime, ncase=5, error=0.04, tracer_names=["kr85","Li"],resolution=10000)
    comp.perform(stime, ncase=5, error=0.001, tracer_names=["cfc11","kr85"],resolution=10000)
    comp.perform(stime, ncase=5, error=0.001, tracer_names=["kr85","Li"],resolution=10000)
    comp.perform(stime, ncase=5, error=0.04, tracer_names=["cfc11","Li"],resolution=10000)
    comp.perform(stime, ncase=5, error=0.001, tracer_names=["cfc11","Li"],resolution=10000)


if __name__ == "__main__":
    # execute only if run as a script
    test_calibration_MH_fuq()
    
    
