# -*- coding: utf-8 -*-
"""
Created on Sun Sep  5 19:22:23 2021

@author: Jean-Raynald de Dreuzy

Tests all programs, applications, benchmarks ... 
Equivalent to non regression test on all possible use of codes

"""

import test_integration as ti
import test_specific_article as tsa
import test_calibration_MH_fuq as tcMS
import benchmark_ploemeur as bp
import benchmark_fontainebleau as bf
import appli_ploemeur as ap
import appli_ploemeur_results_comparison as aprc



# Test of all LPM, Tracers and Calibration codes 
ti.test_integration()

# Tests for the article
tsa.test_specific_article(fuq_n=2,MH_n=2000,init_multiples_n=1)

# Tests comparison between MH and Simplex
tcMS.test_calibration_MH_fuq()

# Benchmark Ploemeur
bp.benchmark_ploemeur()

# Benchmark Fontainebleau
bf.benchmark_fontainebleau()

# Appli Ploemeur
ap.appli_ploemeur()
aprc.appli_ploemeur_results_comparison()
