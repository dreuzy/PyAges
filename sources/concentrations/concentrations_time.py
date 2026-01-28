# -*- coding: utf-8 -*-
"""
Created on Mon Jun  7 04:15:34 2021

@author: Jean-Raynald de Dreuzy
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import tools.figures_additional as figadd
import convolution.convolution_tracers as convolution_tracers
import concentrations.concentrations as c
import global_parameters as gp
import LPM.LPM_generate as lpg

from concentrations.utils.tables import to_cv_dict, merge_model_into_table
from concentrations.utils.distributions import sample_lpms_from_dist
from concentrations.utils.storage import (
    save_concentrations_table,
    save_distributions_tables,
    save_tracer_series_table,
)
from concentrations.utils.plotting import plot_tracer_series, plot_concentration_chronicles


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
        plot_tracer_series(self.cv, axs, graph_type=graph_type)
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
        save_tracer_series_table(self.cv, filename)


def display_concentration_times(
    dir_names,
    lpm,
    display,
    plot=False,
    start_year=1960,
    end_year=None,
    plot_stride=None,
):
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
            craw = c.Concentrations(
                file_load=True,
                file_name=os.path.join(dn, "concentrations.txt"),
            )
            n_tracers = len(craw.cv["element"].unique())
            ncols = 2
            nrows = int(np.ceil(n_tracers / ncols))

            # --- Convolution tracers ---
            tracers = convolution_tracers.ConvolutionTracers(
                names=craw.cv["element"].unique(),
                date=max(craw.cv["date"]),
            )

            # --- Load distribution of parameters ---
            dist = pd.read_table(file, header=0)
            rng = np.random.default_rng(12345)
            array_resolution = 1000
            lpm_number = 10

            lpm_list, pdf, lpm_statistics = sample_lpms_from_dist(
                dist,
                lpm,
                lpm_number=lpm_number,
                array_resolution=array_resolution,
                rng=rng,
            )

            if plot:
                fig, axs = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows))
                conc_data = ConcentrationTime(craw=craw)
                plot_stride = plot_stride or max(lpm_number // 10, 1)
                plot_concentration_chronicles(
                    fig,
                    axs,
                    conc_data,
                    tracers,
                    lpm_list,
                    start_year=start_year,
                    end_year=end_year or max(craw.cv["date"]),
                    plot_stride=plot_stride,
                )
                display.save_and_close(fig, "concentration_times.png", method=method, dpi=300)

            # --- Save PDFs & stats ---
            save_distributions_tables(pdf, lpm_statistics, os.path.join(dn, method))

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

    # Tracers
    tracers = convolution_tracers.ConvolutionTracers(
        names=craw.cv["element"].unique(),
        date=max(craw.cv["date"]),
    )

    # LPM selection
    lpm_list, pdf, lpm_statistics = lpm_results.get_selection(
        lpm_number=lpm_number,
        span_or_suc=span_or_suc,
        array_resolution=1000,
    )

    # merged_all_models accumulera toutes les colonnes des differents modeles
    merged_all_models = None
    plot_stride = max(lpm_number // 10, 1)

    plot_concentration_chronicles(
        fig,
        axs,
        conc_data,
        tracers,
        lpm_list,
        start_year=1960,
        end_year=max(craw.cv["date"]),
        plot_stride=plot_stride,
    )

    for i, lpm in enumerate(lpm_list, start=1):
        concentrations = tracers.convolution_date_range(lpm, 1960, max(craw.cv["date"]))
        cv_dict = to_cv_dict(concentrations)
        merged_all_models = merge_model_into_table(merged_all_models, cv_dict, model_id=i)

    # Finalisation: sauvegarde + fermeture via display_options
    display.save_and_close(fig, filename=os.path.join(method, "concentration_times.png"))

    # Sauvegarde des donnees fusionnees
    outfile_data = os.path.join(display.directory, method, "concentrations_all_models.txt")
    save_concentrations_table(merged_all_models, outfile_data)

    # Sauvegarde distributions
    save_distributions_tables(pdf, lpm_statistics, os.path.join(display.directory, method))
