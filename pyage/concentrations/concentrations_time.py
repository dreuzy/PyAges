# -*- coding: utf-8 -*-
"""
Chronicles and plotting helpers for time-varying concentrations.

Purpose
-------
Provide utilities to reshape concentration observations by tracer over time,
run convolution-based model predictions, and export/plot resulting chronologies.

Author
------
Jean-Raynald de Dreuzy
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import convolution.convolution_tracers as convolution_tracers
import concentrations.concentrations as c

from concentrations.utils.tables import to_cv_dict, merge_model_into_table
from concentrations.utils.distributions import sample_lpms_from_dist
from concentrations.utils.storage import (
    save_concentrations_table,
    save_distributions_tables,
    save_tracer_series_table,
)
from concentrations.utils.plotting import plot_tracer_series, plot_concentration_chronicles


class ConcentrationTime:
    """
    Concentration chronicle, grouped by tracer across time.

    Attributes
    ----------
    craw : Concentrations
        Raw concentration table (long format).
    cv : dict[str, DataFrame]
        Dict of tracer -> DataFrame(date, concentration, element).
    """

    def __init__(self, craw=None, cv=None):
        """
        Build the chronicle either from raw data or from a prepared dict.

        Parameters
        ----------
        craw : Concentrations, optional
            Raw concentration table to reshape by tracer.
        cv : dict[str, DataFrame], optional
            Precomputed tracer tables.
        """
        if craw is not None:
            self.craw = craw
        if cv is None:
            self.build()
        else:
            self.cv = cv
        

    def display(self, fig, axs, graph_type="scatter"): 
        """
        Plot tracer concentration series on provided axes.

        Parameters
        ----------
        fig : matplotlib.figure.Figure
            Figure object used for the plot title.
        axs : array-like
            Axes grid to draw into.
        graph_type : str, optional
            Plot style (e.g., "scatter" or "line").
        """
        plot_tracer_series(self.cv, axs, graph_type=graph_type)
        fig.suptitle("Tracer", fontsize=16, y=1.02)

        
    def build(self):
        """
        Reshape raw concentrations into tracer-specific tables.
        """
        tracers = self.craw.cv["element"].unique()
        self.cv = {}
        for tracer in tracers:
            self.cv[tracer] = self.craw.cv[self.craw.cv["element"] == tracer]
    
    
    def display_model(self, lpm, tracer):
        """
        Placeholder for model visualization (reserved for future use).
        """
        # TODO: compute and display model predictions for a given tracer.
       

    def save_to_file(self, filename):
        """
        Save the tracer chronicle to a single table.

        Parameters
        ----------
        filename : str or Path
            Output file path (TSV).
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
    Display/export concentration chronologies for multiple result folders.

    Parameters
    ----------
    dir_names : list[str]
        Directories containing calibration outputs and concentrations.txt.
    lpm : LPM
        Template LPM structure.
    display : display_options
        Controls figure save/close behavior.
    plot : bool, optional
        Whether to generate and save plots.
    start_year : int or float, optional
        Start year for the plotting range.
    end_year : int or float, optional
        End year for the plotting range; defaults to max observation year.
    plot_stride : int, optional
        Plot every N-th LPM realization (controls plot density).
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

def display_concentration_chronicles(
    craw,
    lpm_results,
    method,
    display,
    time_span_mode,
    lpm_number,
):
    """
    Display tracer chronologies (data + model realizations) and export tables.

    Parameters
    ----------
    craw : Concentrations
        Tracer concentrations table.
    lpm_results : LpmDist
        LPM parameter distribution.
    method : str
        Label used for output folder/filenames.
    display : display_options
        Display options (save/close behavior).
    time_span_mode : str
        Selection mode for LPM sampling ("span" or "successive" variants).
    lpm_number : int
        Number of LPM realizations to sample.

    Figures
    -------
    One figure containing tracer subplots.
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
        time_span_mode=time_span_mode,
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
