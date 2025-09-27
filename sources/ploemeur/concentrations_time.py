# -*- coding: utf-8 -*-
"""
Created on Mon Jun  7 04:15:34 2021

@author: dreuzy
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

import tools.figures_additional as figadd
import convolutions.convolution_tracers as convolution_tracers
import convolutions.concentrations as c
import global_parameters as gp
import LPM.LPM_generate as lpg

import ploemeur.appli_ploemeur_tools as appli_ploemeur_tools


class ConcentrationTime:
    """ Chronicle of concentrations with time 
    """
    def __init__(self,craw=None,cv=None):
        """ 
        craw: inpout concentrations
        c: concentrations as a function of time 
        """
        if craw != None : 
            self.craw=craw
        if cv == None : 
            self.build()
        else : 
            self.cv=cv
        
    def display(self,fig,axs,graph_type="scatter"): 
        """ 
        Displays concentrations 
        """
        gi={}; gj={}
        k=0
        for temp in self.cv :
            if(k<2): gi[temp] = k%2; gj[temp]=0
            else: gi[temp]=(k-2)%2; gj[temp]=1
            axs[gi[temp],gj[temp]].set_title(temp)
            date=self.cv[temp]['date']
            conc=self.cv[temp]['concentration']
            if graph_type == "scatter": 
                axs[gi[temp],gj[temp]].scatter(date,conc,label=temp)
            else : 
                axs[gi[temp],gj[temp]].plot(date,conc,label=temp)
            k=k+1
        fig.suptitle('Tracer')
        # figManager = plt.get_current_fig_manager()
        # figManager.window.showMaximized()
        
        
    def build(self):
        """ Builds concentrations as a function of time """
        tracers=self.craw.cv['element'].unique()
        self.cv={}
        for t in tracers: 
            self.cv[t]=self.craw.cv[self.craw.cv['element'] == t]
    
    
    def display_model(self, lpm, tracer):
        """ computes and displays the models """
        # Loads the tracers
        # 
       
    def save_to_file(self, filename):
        """
          Sauvegarde les concentrations self.cv dans un fichier unique,
          avec la colonne 'date' commune et une colonne par traceur.
        """
      
        # Construire une table avec toutes les colonnes alignées sur 'date'
        merged = None
        for tracer, df in self.cv.items():
            # On garde uniquement 'date' et 'concentration'
            temp = df[['date', 'concentration']].rename(columns={'concentration': tracer})
            if merged is None:
                merged = temp
            else:
                merged = pd.merge(merged, temp, on="date", how="outer")
      
        # Sauvegarde en TSV (tab-separated)
        merged.to_csv(filename, sep="\t", index=False, encoding="utf-8")
        
        
def display_concentration_times(dir_names,lpm,display): 
    """
    Diplays concentrations with time for each of the cases of dir_names 
    
    Arguments 
    ---------
    dir_names: array of str
        List of directory names 
    lpm: LPM
        Template LPM structure 
    display: ?? #JR
    """
    
    # Loop over folders 
    for dn in dir_names :
        # Loop over the methods
        methods=["Metropolis_Hastings","forward_uncertainty_quantification"]
        for method in methods: 
            file=os.path.join(dn,method,"lpm_dist_calibrated.txt")
            # print(dn,'\t',method)
            # print(file)
            if os.path.exists(file): 
                # Initialization of figure 
                fig, axs = plt.subplots(2,2) #len(param_names))

                # Concentrations Data; craw: raw data; conc_data: organized data 
                craw=c.Concentrations(file_load=True, file_name=os.path.join(dn,"concentrations.txt"))
                conc_data=ConcentrationTime(craw=craw)
                conc_data.display(fig,axs,graph_type="scatter")
                tracers = convolution_tracers.ConvolutionTracers(names=craw.cv['element'].unique(),date=max(craw.cv['date'])) 

                #tracers.display(display)                
                # LPM Distribution of solution sets of parameters 
                dist=pd.read_table(file,header=0)                
                rng = np.random.default_rng(12345)
                array_resolution=1000
                lpm_number=10
                # Storage Structures for the lpm_number selected models 
                pdf_t=gp.arange_n(0,70,array_resolution-1) # Between 0 and 70 years
                # Storage strucutre of the pdfs
                pdf_array=np.empty((lpm_number+1,array_resolution))
                pdf_array[0,:]=pdf_t
                aa=[]; aa.append('t')
                # Storage strucutre of the pdf statistics
                lpm_statistics = pd.DataFrame(index=range(lpm_number),columns=lpm.moments_name())
                # Loop on the lpm_number models 
                for i in range(1,lpm_number+1):
                    # Selects line and updates lpm parameters accordingly 
                    [test,line]=lpm.load_lpm_from_dist(dist,option="random_line",rng=rng)
                    if test == True : 
                        # Convolution of LPM with tracer chronicles on the 1960,max(date range)
                        concentrations=tracers.convolution_date_range(lpm,1960,max(craw.cv['date']))
                        # Initialization of ConcentrationTime
                        conc_model=ConcentrationTime(cv=concentrations)
                        # Displays modeled concentrations 
                        conc_model.display(fig,axs,graph_type="line")
                        # Computes and stores pdfs
                        pdf_val=lpm.pdf(pdf_t)
                        pdf_array[i,:]=pdf_val
                        aa.append('p'+str(line))
                        # Computes and sores moments
                        lpm_statistics.iloc[i-1] = lpm.moments()
                    else: 
                        aa.append('p')
                if display.figure_save :
                    plt.savefig(os.path.join(dn,method,"concentration_times"),dpi=300)
                if display.figure_close:
                    plt.close()

                # Outputs of pdfs and moments 
                df=pd.DataFrame(pdf_array.T)
                df.columns=aa
                df.to_csv(os.path.join(dn,method,"distributions.txt"),sep='\t')
                lpm_statistics.to_csv(os.path.join(dn,method,"distributions_stats.txt"),sep='\t')


def to_cv_dict(concentrations):
    """
    Normalise 'concentrations' en dict {tracer: DataFrame(date, concentration, element)}.
    - Si c'est déjà un dict: on le renvoie tel quel.
    - Si c'est un DataFrame 'long' avec une colonne 'element': on split par traceur.
    """
    if isinstance(concentrations, dict):
        return concentrations
    if isinstance(concentrations, pd.DataFrame):
        if not {"date", "concentration", "element"}.issubset(concentrations.columns):
            raise ValueError("Le DataFrame doit contenir les colonnes 'date', 'concentration', 'element'.")
        cv = {}
        for t, grp in concentrations.groupby("element"):
            cv[t] = grp[["date", "concentration", "element"]].reset_index(drop=True)
        return cv
    raise TypeError("Format de 'concentrations' non supporté (dict attendu ou DataFrame avec 'element').")


def merge_model_into_table(merged, cv_dict, model_id):
    """
    Fusionne les concentrations d'un modèle dans un tableau large.
    - merged: DataFrame existant (ou None la première fois), contenant 'date' + colonnes *_<id précédents>
    - cv_dict: dict {tracer: df(date, concentration, element)} pour le modèle courant
    - model_id: entier (1,2,3,...) suffixé aux noms de colonnes, ex: cfc11_9
    Retourne le DataFrame fusionné.
    """
    # Commencer à partir d'un DF vide avec 'date' si nécessaire
    if merged is None:
        # Prendre la 1ère série comme base « date »
        first_df = next(iter(cv_dict.values()))
        merged = first_df[["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)

    # Ajouter toutes les colonnes tracer_modelid
    for tracer, df in cv_dict.items():
        temp = (
            df[["date", "concentration"]]
            .rename(columns={"concentration": f"{tracer}_{model_id}"})
        )
        merged = pd.merge(merged, temp, on="date", how="outer")

    # Trier par date (au cas où)
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def save_concentrations_table(merged, filepath):
    """
    Sauvegarde le tableau large 'merged' en TSV (une seule fois).
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(filepath, sep="\t", index=False, encoding="utf-8")


def display_concentration_chronicles(craw,lpm_results,method,display,span_or_suc,lpm_number):
    """
    Displays the tracer concentration chronicle convolved with the lpm solutions
        craw -> tracers 
        lpm_results -> parameters of lpm
    Displays also the concentration data
        craw

    Parameters
    ----------
    craw : Concentrations
        Tracers and Concentrations
    lpm_results : LPMDist
        Results structure of LPMs
    display : display_options
        Necessary display options

    Figures
    -------
    1 figure by tracer 
    As many figures as tracers
    """
    
    # Figure initialization
    fig, axs = plt.subplots(2,2) #len(param_names))

    # Concentrations Data; craw: raw data; conc_data: organized data 
    conc_data=ConcentrationTime(craw=craw)
    conc_data.display(fig,axs,graph_type="scatter")
    tracers = convolution_tracers.ConvolutionTracers(names=craw.cv['element'].unique(),date=max(craw.cv['date'])) 
    #tracers.display(display)         
       
    # LPM selection
    [lpm_list, pdf, lpm_statistics]=lpm_results.get_selection(lpm_number=lpm_number,span_or_suc=span_or_suc,array_resolution=1000)
    
    # merged_all_models accumulera toutes les colonnes des différents modèles
    merged_all_models = None
    
    for i, lpm in enumerate(lpm_list, start=1):
        # Convolutions → sorties « au début de la boucle »
        concentrations = tracers.convolution_date_range(lpm, 1960, max(craw.cv["date"]))
        # Initialization of ConcentrationTime
        conc_model=ConcentrationTime(cv=concentrations)
        # Displays modeled concentrations 
        conc_model.display(fig,axs,graph_type="line")
    
        # Normaliser en dict {traceur: df(date, concentration, element)}
        cv_dict = to_cv_dict(concentrations)
    
        # (optionnel) affichage des courbes du modèle i, si tu en as besoin
        # plot_model(cv_dict, model_id=i)  # <-- fonction à toi, hors de la classe, si désiré
    
        # Accumuler dans le tableau large
        merged_all_models = merge_model_into_table(merged_all_models, cv_dict, model_id=i)
    
    # Finalization of figure
    display.figure_close_fx(os.path.join(method,"concentration_times"))
    
    # 👉 Une fois la boucle terminée, on écrit un seul fichier avec TOUTES les colonnes
    outfile = os.path.join(display.directory, method, "concentrations_all_models.txt")
    save_concentrations_table(merged_all_models, outfile)
    # print(f"✅ Concentrations de {len(lpm_list)} modèles écrites dans : {outfile}")
    
    
    # # Displays chronicles Loop over the selected lpms 
    # for i, lpm in enumerate(lpm_list, start=1):
    #     # Convolution of LPM with tracer chronicles on the 1960,max(date range) #JR1: 1960?
    #     concentrations=tracers.convolution_date_range(lpm,1960,max(craw.cv['date']))
    #     # Initialization of ConcentrationTime
    #     conc_model=ConcentrationTime(cv=concentrations)
    #     # Displays modeled concentrations 
    #     conc_model.display(fig,axs,graph_type="line")
    #     filename = f"concentrations_export_{i}.txt"
    #     conc_model.save_to_file(os.path.join(display.directory,method,f"conc_{i}.txt"))
    # # Finalization of figure
    # display.figure_close_fx(os.path.join(method,"concentration_times"))

    # Displays pdfs. Loop over the selected lpms 
    figadd.figure_init(figname="pdfs")
    for key in pdf.keys():
        # Convolution of LPM with tracer chronicles on the 1960,max(date range) #JR1: 1960?
        if key != 't': plt.plot(pdf['t'],pdf[key],label=key)
        # Initialization of ConcentrationTime
    # Finalization of figure
    display.figure_close_fx(os.path.join(method,"pdfs"))

    # Outputs
    pdf.to_csv(os.path.join(display.directory,method,"distributions.txt"),sep='\t')
    lpm_statistics.to_csv(os.path.join(display.directory,method,"distributions_stats.txt"),sep='\t')



def test():
    """ Test of loading and displaying function """
    well="F09"
    dates="2005_2020"
    fig, axs = plt.subplots(2,2) #len(param_names))
    craw=appli_ploemeur_tools.ploemoeur_concentrations_ori(well,dates)
    conc_data=ConcentrationTime(craw=craw)
    conc_data.display(fig,axs,graph_type="scatter")
    # lpm test
    lpm=lpg.LPM_generate("exp_shifted")
    # Loads the tracers
    tracers = convolution_tracers.ConvolutionTracers(names=craw.cv['element'].unique(),date=2010)
    display = gp.display_options()
    display.text = False
    display.figure = True
    display.figure_close = False
    display.figure_save = False  
    #tracers.display(display)
    concentrations=tracers.convolution_date_range(lpm,1960,2020.5)
    conc_model=ConcentrationTime(c=concentrations)
    conc_model.display(fig,axs,graph_type="line")

    # conc.display_model(lpm, tracer)
    