# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Chronicles and plotting helpers for time-varying concentrations.

Purpose
-------
Provide utilities to reshape concentration observations by tracer over time,
run convolution-based model predictions, and export/plot resulting chronologies.

"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import pyages.convolution.convolution_tracers as convolution_tracers
from pyages.concentrations.concentrations import Concentrations
from pyages.concentrations.utils.plotting import (
    plot_concentration_chronicles,
    plot_concentration_chronicles_summary,
    plot_tracer_series,
)
from pyages.concentrations.utils.storage import (
    save_concentrations_table,
    save_distributions_tables,
    save_tracer_series_table,
)
from pyages.concentrations.utils.tables import merge_model_into_table, to_cv_dict
from pyages.data_io.lpm_distribution import read_distribution
from pyages.lpm.samples.analysis import select_model_realizations

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from pyages.config.runtime import DisplayOptions
    from pyages.lpm.core.lpm_base import LpmBase
    from pyages.lpm.samples.table import LpmSampleTable


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

    def __init__(
        self,
        craw: Concentrations | None = None,
        cv: Mapping[str, pd.DataFrame] | pd.DataFrame | None = None,
    ) -> None:
        """
        Build the chronicle either from raw data or from a prepared dict.

        Parameters
        ----------
        craw : Concentrations, optional
            Raw concentration table to reshape by tracer.
        cv : dict[str, DataFrame], optional
            Precomputed tracer tables.

        Raises
        ------
        ValueError
            If neither or both input representations are supplied.
        """
        if (craw is None) == (cv is None):
            raise ValueError("Provide exactly one of craw or cv")
        if craw is not None:
            if not isinstance(craw, Concentrations):
                raise TypeError("craw must be a Concentrations instance")
            self.craw = craw
            self.cv = to_cv_dict(craw.cv)
            return
        self.cv = to_cv_dict(cv)

    def display(
        self,
        fig: Figure,
        axs: Axes | Sequence[Axes],
        graph_type: Literal["scatter", "line"] = "scatter",
    ) -> None:
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

    def build(self) -> None:
        """Rebuild defensive tracer-specific tables from raw concentrations."""
        if not hasattr(self, "craw"):
            raise RuntimeError("build() requires a chronicle created from craw")
        self.cv = to_cv_dict(self.craw.cv)

    def save_to_file(self, filename: str | Path) -> None:
        """
        Save the tracer chronicle to a single table.

        Parameters
        ----------
        filename : str or Path
            Output file path (TSV).
        """
        save_tracer_series_table(self.cv, filename)


def display_concentration_times(
    dir_names: Sequence[str | Path],
    lpm: LpmBase,
    display: DisplayOptions,
    plot: bool = False,
    start_year: float = 1960,
    end_year: float | None = None,
    plot_stride: int | None = None,
) -> None:
    """
    Display/export concentration chronologies for multiple result folders.

    Parameters
    ----------
    dir_names : list[str]
        Directories containing calibration outputs and concentrations.txt.
    lpm : LPM
        Template LPM structure.
    display : DisplayOptions
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
    if plot_stride is not None and (
        isinstance(plot_stride, bool)
        or not isinstance(plot_stride, int)
        or plot_stride < 1
    ):
        raise ValueError("plot_stride must be a positive integer or None")
    methods = ["Metropolis_Hastings", "forward_uncertainty_quantification"]

    for dn in dir_names:
        result_directory = Path(dn)
        for method in methods:
            method_directory = result_directory / method
            distribution_file = method_directory / "lpm_dist_calibrated.txt"
            if not distribution_file.exists():
                continue

            # --- Load concentration data ---
            craw = Concentrations.from_file(result_directory / "concentrations.txt")
            n_tracers = len(craw.cv["element"].unique())
            ncols = 2
            nrows = int(np.ceil(n_tracers / ncols))

            # --- Convolution tracers ---
            tracers = convolution_tracers.ConvolutionTracers(
                names=craw.cv["element"].unique(),
                date=max(craw.cv["date"]),
            )

            # --- Load distribution of parameters ---
            dist = read_distribution(distribution_file)
            array_resolution = 1000
            lpm_number = 10

            lpm_list, pdf, lpm_statistics = select_model_realizations(
                lpm,
                dist,
                count=lpm_number,
                resolution=array_resolution,
            )

            if plot:
                fig, axs = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows))
                conc_data = ConcentrationTime(craw=craw)
                effective_stride = plot_stride or max(lpm_number // 10, 1)
                final_year = end_year if end_year is not None else max(craw.cv["date"])
                plot_concentration_chronicles(
                    fig,
                    axs,
                    conc_data,
                    tracers,
                    lpm_list,
                    start_year=start_year,
                    end_year=final_year,
                    plot_stride=effective_stride,
                )
                display.save_and_close(
                    fig, "concentration_times.png", method=method, dpi=300
                )

            # --- Save PDFs & stats ---
            save_distributions_tables(pdf, lpm_statistics, method_directory)


def display_concentration_chronicles(
    craw: Concentrations,
    lpm_results: LpmSampleTable,
    method: str,
    display: DisplayOptions,
    lpm_number: int,
) -> None:
    """
    Display tracer chronologies (data + model realizations) and export tables.

    Parameters
    ----------
    craw : Concentrations
        Tracer concentrations table.
    lpm_results : LpmSampleTable
        LPM parameter distribution.
    method : str
        Label used for output folder/filenames.
    display : DisplayOptions
        Display options (save/close behavior).
    lpm_number : int
        Number of LPM realizations to sample.

    Figures
    -------
    One figure containing tracer subplots.
    """
    if isinstance(lpm_number, bool) or not isinstance(lpm_number, int):
        raise TypeError("lpm_number must be an integer")
    if lpm_number < 1:
        raise ValueError("lpm_number must be at least 1")
    tracer_names = craw.cv["element"].unique()

    # Tracers
    tracers = convolution_tracers.ConvolutionTracers(
        names=tracer_names,
        date=max(craw.cv["date"]),
    )

    # LPM selection
    lpm_list, pdf, lpm_statistics = lpm_results.select(
        count=lpm_number,
        resolution=1000,
    )
    if not lpm_list:
        raise ValueError("The LPM result table did not yield any model realizations")

    # merged_all_models accumulera toutes les colonnes des differents modeles
    merged_all_models = None
    if display.figure:
        n_tracers = len(tracer_names)
        ncols = min(3, max(n_tracers, 1))
        nrows = int(np.ceil(n_tracers / ncols))
        fig, axs = plt.subplots(
            nrows,
            ncols,
            figsize=(6.3 * ncols, 4.0 * nrows),
        )
        plot_concentration_chronicles_summary(
            axs,
            craw,
            tracers,
            lpm_list,
            start_year=1960,
            end_year=max(craw.cv["date"]),
        )

    for i, lpm in enumerate(lpm_list, start=1):
        concentrations = tracers.convolve_date_range(lpm, 1960, max(craw.cv["date"]))
        cv_dict = to_cv_dict(concentrations)
        merged_all_models = merge_model_into_table(
            merged_all_models, cv_dict, model_id=i
        )

    # Finalisation: sauvegarde + fermeture via display_options
    if display.figure:
        display.save_and_close(
            fig,
            filename=str(Path(method) / "concentration_times.png"),
        )

    # Sauvegarde des donnees fusionnees
    outfile_data = Path(display.directory) / method / "concentrations_all_models.txt"
    save_concentrations_table(merged_all_models, outfile_data)

    # Sauvegarde distributions
    save_distributions_tables(pdf, lpm_statistics, Path(display.directory) / method)
