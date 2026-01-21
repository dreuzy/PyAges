# -*- coding: utf-8 -*-
"""
Created on Mon Jun  7 04:42:59 2021

@author: Jean-Raynald de Dreuzy
"""

import os
from pathlib import Path

import global_parameters as gp
import convolutions.concentrations as co


def ploemeur_data_folder(): 
    """

    Returns
    -------
    Root Data Folder of Ploemeur Data

    """
    return os.path.join(gp.ROOT_DIRECTORY, "sites", "ploemeur", "data")


def ploemeur_results_folder(file_root):
    """

    Returns
    -------
    directory_results: str
        Output directory to be used for results

    """
    dir_root = gp.results_directory(gp.ROOT_DIRECTORY_RESULTS,file_root)
    date_file = gp.name_dhms()
    directory_results = gp.results_directory(dir_root,date_file)
    return [directory_results,dir_root,date_file]


def ploemeur_file_ori(well,dates): 
    """ 
    Returns name of original data file of Ploemeur 
        eg: ori_ploemeur_F09_2005_2020.txt
    
    Parameters
    ----------
    well: str
        well name
    dates: str
        Min_Max years in the format: 2005_2020
    
    Returns
    -------
    file_ploemeur: str
        Full folder and file name 
    
    """
    directory = ploemeur_data_folder()
    file_ploemeur = os.path.join(directory,"ori_ploemeur_" + well + "_" + dates + ".txt") 
    return file_ploemeur


def ploemoeur_concentrations_ori(well,dates):
    """ 
    Loads original concentrations of Ploemeur 
        Example of file 
        element	concentration	  error	unit	date
        cfc11	278.107378755613	0	0	2005.517808219178
        cfc12	661.141115421665	0	0	2005.517808219178
        cfc113	99.8644758094094	0	0	2005.517808219178
        cfc11	241.232924731756	0	0	2006.5863013698631
        cfc12	464.925516306645	0	0	2006.5863013698631
        cfc113	78.5956915765017	0	0	2006.5863013698631
        cfc11	273.552455177377	0	0	2007.2191780821918
        cfc12	425.200436420999	0	0	2007.2191780821918
        cfc113	72.0347865199413	0	0	2007.2191780821918
        cfc11	239.448436376084	0	0	2007.978082191781
        cfc12	539.430272948373	0	0	2007.978082191781
        cfc113	77.9083384910316	0	0	2007.978082191781
        cfc11	234.375116574465	0	0	2010.9753424657533
        cfc12	476.387634604424	0	0	2010.9753424657533
        cfc113	68.5511120092745	0	0	2010.9753424657533
        cfc11	242.724123891551	0	0	2013.9232876712329
        cfc12	549.751432422357	0	0	2013.9232876712329
    
    Parameters
    ----------
    well: str
        well name
    dates: str
        Min_Max years in the format: 2005_2020
    
    Returns
    -------
    concentration_sampled: Concentrations Class
        Concentrations in lines 
    
    """
    file_ploemeur = ploemeur_file_ori(well,dates) 
    concentration_sampled=co.Concentrations(file_load=True, file_name=file_ploemeur)
    return concentration_sampled

