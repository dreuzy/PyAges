# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 22:05:45 2021

@author: dreuzy
"""
import sys                                             # sys: abort code

import global_parameters as gp

from LPM.LPM_dirac import LPM_dirac                        # LPM dirac
from LPM.LPM_dirac_double import LPM_dirac_double          # LPM dirac double
from LPM.LPM_dirac_double_1_set import LPM_dirac_double_1_set          # LPM dirac double
from LPM.LPM_exp import LPM_exp                            # LPM exponential
from LPM.LPM_exp_shifted import LPM_exp_shifted            # LPM shifted exponential
from LPM.LPM_uniform import LPM_uniform                    # LPM uniform
from LPM.LPM_ig import LPM_ig                              # LPM inverse gaussian
from LPM.LPM_ig_shifted import LPM_ig_shifted              # LPM inverse gaussian shifted
from LPM.LPM_gamma import LPM_gamma                        # LPM gamma
from LPM.LPM_mix_exp_shifted import LPM_mix_exp_shifted


def LPM_generate(lpm_type,directory_lpm=gp.directory_lpm_data):
    """ 
    Generation of LPM (constructor)
    
    Arguments
    ---------
    lpm_type: str
        name of LPM to generate
    directory_lpm: str 
        name of directory if not default one
        
    Return
    ------
    lpm: LPM
        Lumped Parameter Model (used as mother class LPM and not daughter class)
    
    """
    # Selects and generates LPM
    if(lpm_type=='exp'): 
        lpm = LPM_exp(directory_lpm=directory_lpm)
    elif(lpm_type=='exp_shifted'): 
        lpm = LPM_exp_shifted(directory_lpm=directory_lpm)
    elif(lpm_type=='mix_exp_shifted'): 
        lpm = LPM_mix_exp_shifted(directory_lpm=directory_lpm)
    elif(lpm_type=='dirac'): 
        lpm = LPM_dirac(directory_lpm=directory_lpm)
    elif(lpm_type=='dirac_double'): 
        lpm = LPM_dirac_double(directory_lpm=directory_lpm)
    elif(lpm_type=='dirac_double_1_set'): 
        lpm = LPM_dirac_double_1_set(directory_lpm=directory_lpm)
    elif(lpm_type=='uniform'): 
        lpm = LPM_uniform(directory_lpm=directory_lpm)
    elif(lpm_type=='ig'): 
        lpm = LPM_ig(directory_lpm=directory_lpm)
    elif(lpm_type=='ig_shifted'): 
        lpm = LPM_ig_shifted(directory_lpm=directory_lpm)
    elif(lpm_type=='gamma'): 
        lpm = LPM_gamma(directory_lpm=directory_lpm)
    else:
        print('ERROR Unknown LPM type', lpm_type)
        sys.exit()
    return lpm
        

def LPM_generate_random_uniform(lpm_type,rng=None,directory_lpm=gp.directory_lpm_data):
    """ 
    Generation of LPM (constructor)
        and random uniform distribution of its parameters within their bounds
    
    Arguments
    ---------
    lpm_type: str
        name of LPM to generate
    rng: 
        random number generator 
    directory_lpm: str 
        name of directory if not default one
        
    Return
    ------
    lpm: LPM
        Lumped Parameter Model (used as mother class LPM and not daughter class)
    
    """
    # Builds lpm
    lpm=LPM_generate(lpm_type,directory_lpm)
    # Random uniform choice of parameters
    lpm.random_uniform(rng)
    # Returns lpm
    return lpm


def test(lpm_type,display_options):
    """ 
    Tests generation and displays LPM
    """
    lpm = LPM_generate_random_uniform(lpm_type)
    lpm.moments()
    if display_options.figure : 
        lpm.display_pdf_cdf(display_options)
    if display_options.text : 
        lpm.display(display_options)
        lpm.display_moments()
        