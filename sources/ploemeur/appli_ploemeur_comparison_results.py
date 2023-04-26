# -*- coding: utf-8 -*-
"""
Created on Mon Jun  7 04:15:34 2021

@author: dreuzy
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np



# Class to store a single set of simulation results
class sim_results: 
    def __init__(self,directory,model_name):
        """ 
        craw: inpout concentrations
        c: concentrations as a function of time 
        """


class sim_tree: 
    """
    Simulation Tree within targeted directory
    """
    def __init__(self, directory): 
        self.directory = directory
        self.folders=[]
        self.wells=[]
        self.model_names={}
        self.models=[]
        
        
    def load(self): 
        """
        Loads Simulations within the Tree 
        """
        # Gets the list of first level directory
        dlist = inventory(self. directory)
        for d in dlist: 
            self.folders.append(d)
            # Gets the well 
            for f in os.listdir(d):
                if(os.path.isdir(d+"/"+f)): 
                    well_temp=f[:f.find("_")]
                    self.wells.append(well_temp)
                    break
            # Gets the model_names
            self.model_names[well_temp]=[]
            for f in os.listdir(d): 
                if(f.find("perf.png")>0): 
                    model_temp=f[:f.find("perf.png")-1]
                    self.model_names[well_temp].append(model_temp)
                    self.models=sim_results(d,model_temp)


    def display(self): 
        for (folder,well) in zip(self.folders,self.wells): 
            print(folder,"\n",well,"\n",self.model_names[well],"\n")


def inventory(directory): 
    "Lists all simulation results within a given directory"
    dlist=[]
    for file in os.listdir(directory):
        d = os.path.join(directory, file)
        if os.path.isdir(d):
            # print(d)
            dlist.append(d)
    return dlist


def simulation_types(directory): 
    "Gets all simulations within directory"
    inventory(directory)


if __name__ == "__main__":  
    root = "D:/results/PyAge"
    simul = []
    simul.append(root + "/" + "ploemeur_09_2_0.15all")
    simul.append(root + "/" + "ploemeur_09_2_0.15suc")
    # Loads all simulation results and organize them
    for s in simul :
        st = sim_tree(s)
        st.load()
        st.display()
    