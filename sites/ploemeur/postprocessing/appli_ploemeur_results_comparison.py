import sys
from pathlib import Path

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports

ensure_repo_imports()

# -*- coding: utf-8 -*-
"""
Created on Thu Jun  3 05:13:16 2021

@author: Jean-Raynald de Dreuzy
"""

import copy
import pandas as pd
import os

import matplotlib.pyplot as plt
import numpy as np

from pyage.concentrations import concentrations_time as ct
import pyage.lpm.lpm_build as lpg
import pyage.global_parameters as gp                          # Global variables
import pyage.tools.figures_additional as fad




def edges_to_nodes(edges): 
    nodes=[]
    for i in range(len(edges)-1):
        nodes.append((edges[i]+edges[i+1])/2)
    return nodes


def dir_list(date_sim,distribution,dir_ploemeur_root):        
    """ Returns list of directories in "date_sim" directory """
    # dir_ploemeur=os.path.join(gp.ROOT_DIRECTORY_RESULTS,"ploemeur_single",date_sim)
    dir_ploemeur=os.path.join(dir_ploemeur_root,date_sim)
    temp=os.listdir(dir_ploemeur)
    dir_names=[]
    for i in temp:
        if os.path.isdir(os.path.join(dir_ploemeur,i)):
            dir_names.append(i)
    well_date=copy.deepcopy(dir_names)
    for k in range(len(dir_names)):
        dir_names[k]=os.path.join(dir_ploemeur,dir_names[k],distribution)
    return dir_names,well_date,dir_ploemeur


def load_param_distributions(dir_names,option):
    """ Loads distributions of parameters """
    if option == "distribution": 
        dist_list=[]
        for dn in dir_names :
            # Gets to the file0]
            file=os.path.join(dn,"Metropolis_Hastings","lpm_dist_calibrated.txt")
            # print(file)
            if os.path.exists(file): 
                dist_list.append(pd.read_table(file,header=0))
        return dist_list
    elif option == "stats" or option == "stats_quantiles":
        dist_list=[]
        for dn in dir_names :
            # Gets to the file0]
            file=os.path.join(dn,"Metropolis_Hastings","lpm_stats_calibrated.txt")
            # print(file)
            if os.path.exists(file): 
                dist_list.append(pd.read_table(file,header=0))
        return dist_list
    elif option == "perf": 
        dist_list=[]
        for dn in dir_names :
            # Gets to the file0]
            file=os.path.join(dn,"Metropolis_Hastings","results_calibration.txt")
            # print(file)
            if os.path.exists(file): 
                dist_list.append(pd.read_table(file,header=0))
        return dist_list        
    else: 
        print('Problem option for loading data not possible\t', option)


def contactenate_and_save(dists,param_names,well_dates,dir_root,distribution,options): 
    """ Concatenates Results on the means """
    lst =['date']
    list_quant = ["quart10","quart25","median","quart75","quart90"]

    if options == "stats_quantiles":         
        for quart in list_quant: 
            lst.append(quart+"_mean")
            lst.append(quart+"_std")
        
    for pa in param_names :
        lst.append(pa+"_mean")
        lst.append(pa+"_std")
    lst.append("objfunc"+"_mean")
    lst.append("objfunc"+"_std")
    
    df = pd.DataFrame(columns=lst)
    kd=0
    for dist in dists :
        # Loop on parameters 
        year=int(well_dates[kd][-4:])
        lstv=[year]            
        # Parameters
        index_mean = dist.loc[dist.iloc[:,0] == 'mean'].index.tolist()[0]
        index_std = dist.loc[dist.iloc[:,0] == 'std'].index.tolist()[0]
        
        if options == "stats_quantiles":   
            for quart in list_quant:
                lstv.append(dist[quart][index_mean])
                lstv.append(dist[quart][index_std])
                
        for pa in param_names :
            lstv.append(dist[pa][index_mean])
            lstv.append(dist[pa][index_std])
        lstv.append(dist['obj_function'][index_mean])
        lstv.append(dist['obj_function'][index_std])
        df.loc[kd]=lstv
        
        kd=kd+1
        
    df.to_csv(os.path.join(dir_root,distribution+"_"+options+".txt"),sep='\t')
    return df


def display_all(dists,param_names,well_dates,option,distribution,dir_root): 
    """ Display distributions """
    quartiles=['quart25','median','quart75','quart90']
    
    if len(dists)>0 : 
        if option == "perf": 
            fig, axs = plt.subplots(1,2) #len(param_names))
            axs[0].set_title("time")
            axs[1].set_title("success_rate")
            fig.suptitle(distribution)
        elif option == "stats_quantiles": 
            fig, axs = plt.subplots(2,2) #len(param_names))
            gi={}; gj={}
            for k in range(len(quartiles)) :
                temp = quartiles[k]
                if(k<2): gi[temp] = k%2; gj[temp]=0
                else: gi[temp]=(k-2)%2; gj[temp]=1
                axs[gi[temp],gj[temp]].set_title(temp)
            fig.suptitle(distribution)

        else: 
            # Preparation of graphics 
            fig, axs = plt.subplots(2,2) #len(param_names))
            gi={}; gj={}
            for k in range(len(param_names)) :
                temp = param_names[k]
                if(k<2): gi[temp] = k%2; gj[temp]=0
                else: gi[temp]=(k-2)%2; gj[temp]=1
                axs[gi[temp],gj[temp]].set_title(temp)
            gi['objfunc']=1
            gj['objfunc']=1
            axs[gi['objfunc'],gj['objfunc']].set_title('objfunc')
            fig.suptitle('p & J ' + distribution)
        
        plt.subplots_adjust(left=0.1,
                    bottom=0.1, 
                    right=0.9, 
                    top=0.9, 
                    wspace=0.4, 
                    hspace=0.4)
        
        # Loop on all sets of data 
        kd=0
        for dist in dists :
            # Loop on parameters 
            year=int(well_dates[kd][-4:])
            if option =="stats" or option == "distribution": 
                # Parameters
                k = 0
                for pa in param_names :
                    if option == "distribution":
                        aa = np.histogram(dist[pa], bins=50, range=None, weights=None, density=True)
                        val_p=aa[0]
                        val_x=edges_to_nodes(aa[1])
                        axs[gi[pa],gj[pa]].plot(val_x,val_p,label=well_dates[kd])
                    elif option == "stats":
                        index_mean = dist.loc[dist.iloc[:,0] == 'mean'].index.tolist()[0]
                        index_std = dist.loc[dist.iloc[:,0] == 'std'].index.tolist()[0]
                        mean=dist[pa][index_mean]
                        std=dist[pa][index_std]
                        aa = np.histogram(dist[pa], bins=50, range=None, weights=None, density=True)
                        axs[gi[pa],gj[pa]].errorbar(year,mean,std,label=well_dates[kd],fmt="o")
                        axs[gi[pa],gj[pa]].grid(color='k', linestyle='-', linewidth=0.5)
                        #axs[gi[pa],gj[pa]].set_yscale("log")
                    k = k + 1
                # val = dist['obj_function'] #RMSE(dist['obj_function'],(len(dist.columns)-len(param_names)-2))
                # Objective function 
                if option == "distribution":
                    aa = np.histogram(dist['obj_function'], bins=100, range=None, weights=None, density=True)
                    val_x=edges_to_nodes(aa[1])
                    val_p=aa[0]
                    axs[gi['objfunc'],gj['objfunc']].plot(val_x,val_p,label=well_dates[kd])
                elif option == "stats": 
                    index_mean = dist.loc[dist.iloc[:,0] == 'mean'].index.tolist()[0]
                    index_std = dist.loc[dist.iloc[:,0] == 'std'].index.tolist()[0]
                    mean=dist['obj_function'][index_mean]
                    std=dist['obj_function'][index_std]
                    # axs[gi['objfunc'],gj['objfunc']].scatter(year,mean,label=well_dates[kd])
                    axs[gi['objfunc'],gj['objfunc']].errorbar(year,mean,std,label=well_dates[kd],fmt='o')
                    axs[gi['objfunc'],gj['objfunc']].grid(color='k', linestyle='-', linewidth=0.5)
            elif option == "perf": 
                time_perf = float(dist.columns[1])
                success_rate = dist.iloc[0,1]
                axs[0].scatter(year,time_perf,label=well_dates[kd])
                axs[0].grid(color='k', linestyle='-', linewidth=0.5)
                axs[1].scatter(year,success_rate,label=well_dates[kd])
                axs[1].grid(color='k', linestyle='-', linewidth=0.5)
                axs[1].set_yscale("log")
            if option == "stats_quantiles": 
                # Quartiles
                for qua in quartiles :
                    index_mean = dist.loc[dist.iloc[:,0] == 'mean'].index.tolist()[0]
                    index_std = dist.loc[dist.iloc[:,0] == 'std'].index.tolist()[0]
                    mean=dist[qua][index_mean]
                    std=dist[qua][index_std]
                    axs[gi[qua],gj[qua]].errorbar(year,mean,std,label=well_dates[kd],fmt="o")
                    axs[gi[qua],gj[qua]].grid(color='k', linestyle='-', linewidth=0.5)
                    #axs[gi[qua],gj[qua]].set_yscale("log")
            
            plt.legend(fontsize=4,loc='best')
            # plt.grid(color='k', linestyle='-', linewidth=0.5)
            kd=kd+1
        # figManager = plt.get_current_fig_manager()
        # figManager.window.showMaximized()
        fad.figure_close(filename=os.path.join(dir_root,distribution+"_"+option))
  

    
def load_and_display(date_sim,lpm_type,directory): 
    """
    Loads and Displays Data

    Parameters
    ----------
    date_sim : str
        Label of simulation (date), eg '2021_06_30-15_07_38'
    lpm_type : str
        Type of LPM
    directory : str
        root reference directory of results, ef 'C:\\DATA\\results\\PyAge\\ploemeur'

    """
    [dir_names,well_dates,dir_ploemeur]=dir_list(date_sim,lpm_type,directory)
    # Gets lpm_type template and parameter names 
    lpm = lpg.lpm_build(lpm_type,directory_lpm=gp.DIRECTORY_LPM_DATA)
    param_names = lpm.get_param_names()
    
    # Displays concentrations according to time
    display = gp.display_options()
    display.text = False
    display.figure = True
    display.figure_close = True
    display.figure_save = True 
    ct.display_concentration_times(dir_names,lpm,display)
    
    # Loads data from directories
    options=["stats","perf","distribution","stats_quantiles"]
    for option in options:
        dists=load_param_distributions(dir_names,option)
        display_all(dists,param_names,well_dates,option,lpm_type,dir_ploemeur)
        if option=="stats" or option=="stats_quantiles": 
            contactenate_and_save(dists,param_names,well_dates,dir_ploemeur,lpm_type,option)
        
        
        
# ----------------------------------------------
# ----------------- LAUNNCHERS -----------------
# ----------------------------------------------
    
def appli_ploemeur_results_comparison(): 
    # List of directories from which multifold distributions will be loaded
    dir_ploemeurs=[]
    dir_ploemeurs.append(os.path.join(gp.ROOT_DIRECTORY_RESULTS,"ploemeur2"))
    # dir_ploemeurs.append(os.path.join(gp.ROOT_DIRECTORY_RESULTS,"ploemeur_single"))
    # dir_ploemeurs.append(os.path.join(gp.ROOT_DIRECTORY_RESULTS,"ploemeur_all"))
    for dir_ploemeur in dir_ploemeurs: 
        date_sims=os.listdir(dir_ploemeur)
        distributions = ["exp_shifted_old","exp_shifted_young","exp_shifted","exp","dirac_double","dirac","ig","ig_shifted"]
        for date_sim in date_sims:
            for distribution in distributions:
                load_and_display(date_sim,distribution,dir_ploemeur)


if __name__ == "__main__":    
    appli_ploemeur_results_comparison()
