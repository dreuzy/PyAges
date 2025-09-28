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
        
    def display(self, fig, axs, graph_type="scatter"): 
        """Displays concentrations on given axes"""
        axs = axs.flatten()  # simplifie l'indexation
        for k, temp in enumerate(self.cv):
            ax = axs[k]
            ax.set_title(temp)
            date = self.cv[temp]["date"]
            conc = self.cv[temp]["concentration"]
            if graph_type == "scatter": 
                ax.scatter(date, conc, label=temp)
            else: 
                ax.plot(date, conc, label=temp)
            # ax.legend()
    
        fig.suptitle("Tracer", fontsize=16, y=1.02)

        
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
        
        
def display_concentration_times(dir_names, lpm, display): 
    """
    Displays concentrations with time for each case in dir_names.
    
    Parameters
    ----------
    dir_names : list of str
        List of directory names.
    lpm : LPM
        Template LPM structure.
    display : display_options
        Controls figure save/close behavior.
    """
    methods = ["Metropolis_Hastings", "forward_uncertainty_quantification"]

    for dn in dir_names:
        for method in methods:
            file = os.path.join(dn, method, "lpm_dist_calibrated.txt")
            if not os.path.exists(file):
                continue

            # --- Load concentration data ---
            craw = c.Concentrations(file_load=True, 
                                    file_name=os.path.join(dn, "concentrations.txt"))
            conc_data = ConcentrationTime(craw=craw)

            n_tracers = len(craw.cv["element"].unique())
            ncols = 2
            nrows = int(np.ceil(n_tracers / ncols))

            # fig, axs = plt.subplots(nrows, ncols, figsize=(6*ncols, 4*nrows))
            # axs = np.atleast_1d(axs).flatten()

            # --- Scatter plots of measured data ---
            # conc_data.display(fig, axs, graph_type="scatter")

            # --- Convolution tracers ---
            tracers = convolution_tracers.ConvolutionTracers(
                names=craw.cv["element"].unique(),
                date=max(craw.cv["date"])
            )

            # --- Load distribution of parameters ---
            dist = pd.read_table(file, header=0)
            rng = np.random.default_rng(12345)
            array_resolution = 1000
            lpm_number = 10

            pdf_t = gp.arange_n(0, 70, array_resolution - 1)
            pdf_array = np.empty((lpm_number + 1, array_resolution))
            pdf_array[0, :] = pdf_t
            aa = ["t"]

            lpm_statistics = pd.DataFrame(index=range(lpm_number),
                                          columns=lpm.moments_name())

            # --- Loop on models ---
            for i in range(1, lpm_number + 1):
                test, line = lpm.load_lpm_from_dist(dist, option="random_line", rng=rng)
                if not test:
                    aa.append("p")
                    continue

                concentrations = tracers.convolution_date_range(lpm, 1960, max(craw.cv["date"]))
                conc_model = ConcentrationTime(cv=concentrations)
                # conc_model.display(fig, axs, graph_type="line")

                # Store PDFs
                pdf_array[i, :] = lpm.pdf(pdf_t)
                aa.append(f"p{line}")

                # Store moments
                lpm_statistics.iloc[i-1] = lpm.moments()

            # --- Finalize figure ---
            # fig.suptitle(f"Concentration Times – {method}", fontsize=16)
            
            # plt.savefig(os.path.join(dn,method,"concentration_times"),dpi=300)
            # plt.close(fig)
            # display.save_and_close(fig, "concentration_times.png", method=method, dpi=300)

            # --- Save PDFs & stats ---
            df = pd.DataFrame(pdf_array.T, columns=aa)
            df.to_csv(os.path.join(dn, method, "distributions.txt"), sep="\t", index=False)
            lpm_statistics.to_csv(os.path.join(dn, method, "distributions_stats.txt"), sep="\t", index=False)


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


def display_concentration_chronicles(craw, lpm_results, method, display, span_or_suc, lpm_number):
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
    # Figure initialization : 2x2 subplots
    fig, axs = plt.subplots(2, 2, figsize=(10, 8))
    
    # Concentrations Data
    conc_data = ConcentrationTime(craw=craw)
    conc_data.display(fig, axs, graph_type="scatter")
    
    # Tracers
    tracers = convolution_tracers.ConvolutionTracers(
        names=craw.cv["element"].unique(),
        date=max(craw.cv["date"])
    )
    
    # LPM selection
    lpm_list, pdf, lpm_statistics = lpm_results.get_selection(
        lpm_number=lpm_number,
        span_or_suc=span_or_suc,
        array_resolution=1000
    )
    
    # merged_all_models accumulera toutes les colonnes des différents modèles
    merged_all_models = None
    
    for i, lpm in enumerate(lpm_list, start=1):
        # Convolution
        concentrations = tracers.convolution_date_range(lpm, 1960, max(craw.cv["date"]))
        conc_model = ConcentrationTime(cv=concentrations)
    
        # 👉 Affichage seulement une fois sur 5
        if i % 5 == 0:
            conc_model.display(fig, axs, graph_type="line")
    
        # Conversion et accumulation
        cv_dict = to_cv_dict(concentrations)
        merged_all_models = merge_model_into_table(merged_all_models, cv_dict, model_id=i)

    
    # Finalisation → sauvegarde + fermeture via display_options
    display.save_and_close(fig, filename=os.path.join(method, "concentration_times.png"))
    
    # Sauvegarde des données fusionnées
    outfile_data = os.path.join(display.directory, method, "concentrations_all_models.txt")
    save_concentrations_table(merged_all_models, outfile_data)
    # if display.text:
    #     print(f"✅ Concentrations de {len(lpm_list)} modèles écrites dans : {outfile_data}")
    
    # --- PDFs ---
    # fig, ax = figadd.figure_init(figname="pdfs")
    # for key in pdf.keys():
    #     if key != "t":
    #         ax.plot(pdf["t"], pdf[key], label=key)
    
    # display.save_and_close(fig, ax=ax, filename=os.path.join(method, "pdfs.png"))
    
    # Sauvegarde distributions
    pdf.to_csv(os.path.join(display.directory, method, "distributions.txt"), sep='\t')
    lpm_statistics.to_csv(os.path.join(display.directory, method, "distributions_stats.txt"), sep='\t')


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
    