# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 16:26:55 2021

@author: Jean-Raynald de Dreuzy
"""                                        

import global_parameters as gp
import LPM.LPM_generate as LPM_generate
import calibration.workflows.synthetic_test as cst
import calibration.methods.simplex as csimp
import calibration.methods.metropolis_hastings as cMH


class TestIntegration:
    """ 
    Extensive tests for PyAge
    
    Arguments
         ---------
    date: float
        date(year) at which convolutions are computed taken

    Attributes, public
    ----------
    __date: float
        date(year) at which convolutions are computed taken
    LPM_all : array of str
        list of all LPM models 
    LPM_calib : array of str
        list of LPM on which calibration is tested
    tracers_all : array of str
        list of all Tracers
    tracers_conv: array of str
        list of Tracers on which convolution functions are tested
    tracers_calib: array of str
        list of Tracers on which calibration functions are tested
    reachable_resolution : int
        Number of iteration allowed for the computation of reachable concentrations 
    display: display_options
        display options 
    
    Methods (principal)
    -------
    __init__(self)
        Constructor: main parameter tests 
        
    """
    
    def __init__(self,date=2010):
        self.LPM_all = ['dirac','dirac_double','dirac_double_1_set','exp_shifted','dirac','gamma','exp','uniform','ig','ig_shifted','mix_exp_shifted']
        self.LPM_calib = ['dirac_double','exp_shifted','exp','gamma','ig','uniform','dirac_double','dirac']#['dirac_double','dirac','exp','exp_shifted','uniform','gamma','ig']
        self.tracers_all = ["Li","sf6","cfc11","cfc12","cfc113","kr85","3H","14C","39Ar"]
        self.tracers_conv = ["cfc11","kr85"]
        self.tracers_calib = ["cfc11","kr85"]
        # Reachable Concentrations
        self.reachable_resolution = 1000
        # Output options
        self.display = gp.display_options()
        self.display_set(single_all="all")
        self.__date = date


    def display_set(self,single_all="all"): 
        """
        Display options for single or all tests
            single: all display options activated
            all: no options activated
        """
        self.display.figure_save = True  
        self.display.figure = True
        if single_all == "single": 
            self.display.text = True
            self.display.figure_close = True 
        else: 
            self.display.text = False
            self.display.figure_close = True
            

    def folder_results(self,folder_name): 
        """
        Location and creation of results folder 
            gp.ROOT_DIRECTORY_RESULTS//test//folder_name
        """
        directory = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,"test")
        directory = gp.results_directory(directory,folder_name)
        self.display.directory = gp.results_directory(directory,gp.name_dhms())


    def check_lpms(self,single_all="all",single_name=""):
        """ 
        Checks lpms
            Successive "GENERATE", "CONVOLUTION" and "REACHABLE CONCENTRATIONS" 
                testing enables the modulation of the order of functionality tested
            Method with single lpm is used typically when a new lpm is developed 
            
        Arguments
        ---------
        single_all: str
            "single": test for a single lpm
            "all": test for all lpms
        single_name: str
            Name of LPM tested
        """
        
        # Nature of the test
        if single_all == "single":
            lpm_list=[single_name]
        else: 
            lpm_list=self.LPM_all
            
        self.display_set(single_all)
        self.folder_results("integration_LPMs")  
        
        print('\nGENERATE AND DISPLAY LPM') 
        for t in lpm_list:
            LPM_generate.test(t,display_options=self.display)
        

    def check_calibration(self,single_all="all",single_name=""): 
        """ 
        Checks calibration
            All calibration methods checked
            
        Arguments
        ---------
        single_all: str
            "single": test for a single lpm
            "all": all calibrated models
        single_name: str
            Name of lpm 
        """
                
        # Nature of the test
        if single_all == "single":
            lpm_list=[single_name]
        else: 
            lpm_list=self.LPM_calib
            
        self.display_set(single_all)
        self.folder_results("integration_calibration") 

        tracer_names = ["cfc11","Li"]
        # date for each of the tracers 
        date = [1990,2010] 

        print('\nCALIBRATION ON SYNTETIC CASES: METROPOLIS-HASTINGS')
        for lpm in lpm_list:  
            calib_MH = cMH.MetropolisHastings(nstep=2000,prior_option=True,prior_typ="parametric",likelyhood=True,lpm_number=10,monitor=False) 
            calib = cst.CalibrationSyntheticTest(calib_strategy=calib_MH,ncase=2,error=0.03,tracer_names=tracer_names,
                                                 date=date,lpm_type=lpm,display_options=self.display,nmodels=500)
            calib.perform_ncase()

        print('\nCALIBRATION ON SYNTETIC CASES: SIMPLEX_INIT_MULTIPLES')
        for lpm in lpm_list:
            calib_simplex = csimp.Simplex("Simplex_init_multipes",init_multiples_n=10)
            # self.display.text = True
            calib = cst.CalibrationSyntheticTest(calib_strategy=calib_simplex,ncase=2,error=0.001,tracer_names=tracer_names,
                                                 date=date,lpm_type=lpm,display_options=self.display,nmodels=10)
            calib.perform_ncase()
            
        print('\nCALIBRATION ON SYNTETIC CASES: SIMPLEX')
        # Does not work for ig_shifted (3 parameters) and for uniform
        for lpm in lpm_list:
            calib_simplex = csimp.Simplex("Simplex")            
            # self.display.text = True
            calib = cst.CalibrationSyntheticTest(calib_strategy=calib_simplex,ncase=2,error=0.01,tracer_names=tracer_names,
                                                 date=date,lpm_type=lpm,display_options=self.display,nmodels=10)
            calib.perform_ncase()

        print('\nCALIBRATION ON SYNTETIC CASES: FORWARD UNCERTAINTY QUANTIFICATION')
        for lpm in lpm_list:
            calib_simplex = csimp.Simplex("forward_uncertainty_quantification",init_multiples_n=2,fuq_n=2)
            calib = cst.CalibrationSyntheticTest(calib_strategy=calib_simplex,ncase=2,error=0.04,tracer_names=tracer_names,
                                                 date=date,lpm_type=lpm,display_options=self.display)
            calib.perform_ncase()

        # Unit Test of Metropolis Hastings algorithm on simple priors 
        cMH.test_calibration_MH_prior(self.display)

        

# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------

def test_integration(): 
   

    # Simple test functions: exhaustive tracer or lpm
    ti = TestIntegration(date=2010)
    ti.check_lpms(single_all="all")

    # Simple test functions: single tracer or lpm
    ti = TestIntegration(date=2010)
    ti.check_lpms(single_all="single",single_name="dirac_double_1_set")

    # Checks calibration 
    ti = TestIntegration(date=2010)
    #ti.check_calibration(single_all="single",single_name="ig")
    ti.check_calibration(single_all="all")
    # ti.check_calibration(single_all="all")
        
    
if __name__ == "__main__":
    test_integration()
