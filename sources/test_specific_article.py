# -*- coding: utf-8 -*-
"""
Created on Tue May 18 21:10:20 2021

@author: dreuzy
"""

import copy
import matplotlib.pyplot as plt
import pandas as pd
import os 

import global_parameters as gp


import LPM.LPM_generate as lpg
import test_calibration_MH_fuq as troot


# Output in files 
def output_synthesis(lpm_target,lpm_results,concentration_sampled,directory,error,lpm_type): 
             
    for i in range(len(lpm_target)): 
        data={'error':error}
        lpm_results[i][1].get_stats_line(lpm_target[i],data)
        data.update(concentration_sampled[i].export_to_dict())
        # Adds new line
        if i == 0:
            store = pd.DataFrame(data)
        else:
            store = store.append(pd.DataFrame(data))
    
    store.to_csv(os.path.join(directory,"results_"+lpm_type+str(error)+".txt"),sep='\t')

    
# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------

def test_specific_article(fuq_n=10,MH_n=2500,init_multiples_n=1,error=0.4,lpm_type='ig',resolution=1000):    
    simu = troot.comparison_MH_fuq()
    param=[]
    
    # Inverse Gaussian
    if lpm_type == 'ig':
        simu.models_calib=['ig']
        # param.append([5,10]); param.append([15,10]); param.append([20,10]); param.append([30,10]); param.append([40,10])
        # param.append([10,10]); param.append([10,15]); param.append([10,20]); param.append([10,25])
        # param.append([10,5]); param.append([20,5]); param.append([30,5]); param.append([40,5]); param.append([50,5])
        n=5
        for i in range(n):
            for j in range(n): 
                mu=i/n*50
                shift=j/n*50
                if mu+shift<=50: 
                    if mu==0: mu=1
                    if shift==0: shift=1
                    param.append([mu,shift])
        print(param)
    
    # Shifted Exponential
    if lpm_type == 'exp_shifted':
        simu.models_calib=['exp_shifted']
        # n=5
        # for i in range(n):
        #     for j in range(n): 
        #         mu=i/n*50
        #         shift=j/n*50
        #         if mu+shift<=50: 
        #             if mu==0: mu=1
        #             if shift==0: shift=1
        #             param.append([mu,shift])
        # print(param)
        param.append([10,30]); param.append([10,40]); 
        # param.append([20,20]); param.append([30,20]); param.append([40,20])
        # param.append([10,10]); param.append([10,20]); param.append([10,30]); param.append([10,40])
        # param.append([10,5]); param.append([20,5]); param.append([30,5]); param.append([40,5]); param.append([50,5])
    
    # Double Dirac
    if lpm_type == 'dirac_double':
        simu.models_calib=['dirac_double']
        n=5
        for i in range(n):
            for j in range(n): 
                mu1=i/n*50
                mu2=j/n*50
                if mu1+mu2<=50: 
                    if mu1==0: mu1=1
                    if mu2==0: mu2=1
                    param.append([mu1,mu2,0.25])
                    param.append([mu1,mu2,0.5])
                    param.append([mu1,mu2,0.75])
        print(param)
        # param.append([5,20,0.75]); param.append([5,20,0.25]); param.append([10,30,0.75]); param.append([10,30,0.25]); 
        # param.append([20,30,0.75]); param.append([20,30,0.25]); param.append([5,50,0.75]); param.append([5,50,0.5]); 

    lpm_target = lpg.LPM_generate(simu.models_calib[0])
    # Numerical Parameters
    simu.fuq_n = fuq_n 
    simu.init_multiples_n = init_multiples_n 
    simu.MH_n = MH_n

    # Directory
    directory = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,"test_article_loop_3")
    stime = gp.simulation_time(nsim=6)
    
    # Defines Target LPM        
    lpm_target_vec=[]
    for i in range(len(param)):
        lpm_target.set_param_from_array(param[i]); lpm_target_vec.append(copy.deepcopy(lpm_target))
    
    lpm_target=[None]*len(lpm_target_vec)
    lpm_results=[None]*len(lpm_target_vec)
    concentration_sampled=[None]*len(lpm_target_vec)
    lpm_calibration=[None]*len(lpm_target_vec)
    # Runs
    for i in range(len(lpm_target_vec)): 
        simu.directory_root = gp.results_directory(directory,gp.name_dhms()) 
        [lpm_target[i],lpm_results[i],concentration_sampled[i],lpm_calibration[i]]= \
                    simu.perform(stime, ncase=1, error=error, 
                                 tracer_names=["cfc11","cfc12","cfc113","sf6"], 
                                 lpm_random=False, lpm_target=lpm_target_vec[i],resolution=resolution)
        # Points on top of objective function color map
        display=gp.display_options()
        display.figure_close=False
        display.figure_save=True
        lpm_calibration[i][1].analysis_calibration()
        lpm_results[i][1].display_points_alone()
        plt.xlim(0,50);plt.ylim(0,50) 
        plt.savefig(os.path.join(simu.directory_root,"objectivefunction"),dpi=300)
        plt.close()
                    
    # Output in files 
    output_synthesis(lpm_target,lpm_results,concentration_sampled,directory,error,lpm_type)



if __name__ == "__main__":
    error_list=[0.08]#[0.08,0.04,0.16,0.02,0.001]
    for error in error_list: 
        test_specific_article(fuq_n=10,init_multiples_n=1,MH_n=2500,error=error,lpm_type='exp_shifted',resolution=1000) ##
        test_specific_article(fuq_n=100,init_multiples_n=1,MH_n=250000,error=error,lpm_type='ig',resolution=10000)
        test_specific_article(fuq_n=100,init_multiples_n=1,MH_n=250000,error=error,lpm_type='dirac_double',resolution=10000)