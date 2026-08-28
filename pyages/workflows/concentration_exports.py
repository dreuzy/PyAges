# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Orchestrate calibrated LPM chronicle figures and table exports."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np

from pyages._plotting import finalize_figure
from pyages.concentrations import ConcentrationChronicle, Concentrations
from pyages.concentrations.plotting import (
    plot_concentration_chronicles,
    plot_concentration_chronicles_summary,
)
from pyages.concentrations.series import merge_model_into_table, normalize_series
from pyages.concentrations.temporal import (
    evaluate_temporal_predictions,
    summarize_temporal_realizations,
)
from pyages.convolution import ConvolutionTracers
from pyages.data_io.concentrations import (
    save_concentrations_table,
    save_distributions_tables,
)
from pyages.data_io.lpm_distribution import read_distribution
from pyages.lpm.samples.analysis import select_model_realizations

if TYPE_CHECKING:
    from pyages.config.runtime import DisplayOptions
    from pyages.lpm.core.lpm_base import LpmBase
    from pyages.lpm.samples.table import LpmSampleTable


def export_concentration_chronicles(
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
            # A workflow may run only one calibration method; an absent result
            # directory is therefore expected rather than an export failure.
            if not distribution_file.exists():
                continue

            observations = Concentrations.from_file(
                result_directory / "concentrations.txt"
            )
            n_tracers = len(observations.unique_tracer_names())
            ncols = 2
            nrows = int(np.ceil(n_tracers / ncols))

            # Chronicle curves use a common end date so all unique tracers are
            # evaluated on comparable calendar ranges.
            tracers = ConvolutionTracers(
                names=observations.unique_tracer_names(),
                date=max(observations.frame["date"]),
            )
            tracers.validate_observation_units(observations)

            dist = read_distribution(distribution_file)
            array_resolution = 1000
            lpm_number = 10

            # The selector supplies a fixed default random seed, keeping
            # repeated exports of the same result table reproducible.
            lpm_list, pdf, lpm_statistics = select_model_realizations(
                lpm,
                dist,
                count=lpm_number,
                resolution=array_resolution,
            )

            if plot:
                fig, axs = plt.subplots(nrows, ncols, figsize=(6 * ncols, 4 * nrows))
                chronicle = ConcentrationChronicle(observations=observations)
                effective_stride = plot_stride or max(lpm_number // 10, 1)
                final_year = (
                    end_year
                    if end_year is not None
                    else max(observations.frame["date"])
                )
                realizations = evaluate_temporal_predictions(
                    tracers,
                    lpm_list,
                    start_year,
                    final_year,
                )
                plot_concentration_chronicles(
                    fig,
                    axs,
                    chronicle,
                    realizations,
                    plot_stride=effective_stride,
                )
                fig.tight_layout()
                finalize_figure(
                    fig,
                    display.figure_path("concentration_times.png", method=method),
                    close=display.figure_close,
                )

            # Numerical outputs remain available when plotting is disabled,
            # keeping the display policy separate from data export.
            save_distributions_tables(pdf, lpm_statistics, method_directory)


def export_calibrated_chronicles(
    observations: Concentrations,
    lpm_results: LpmSampleTable,
    method: str,
    display: DisplayOptions,
    lpm_number: int,
) -> None:
    """
    Display tracer chronologies (data + model realizations) and export tables.

    Parameters
    ----------
    observations : Concentrations
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
    tracer_names = observations.unique_tracer_names()

    # All unique tracers share the latest observation date because this export
    # evaluates complete histories rather than independent sampling rows.
    tracers = ConvolutionTracers(
        names=tracer_names,
        date=max(observations.frame["date"]),
    )
    tracers.validate_observation_units(observations)

    # Selection is reproducible by default and returns independent model copies,
    # so convolution cannot mutate the stored calibration samples.
    lpm_list, pdf, lpm_statistics = lpm_results.select(
        count=lpm_number,
        resolution=1000,
    )
    if not lpm_list:
        raise ValueError("The LPM result table did not yield any model realizations")

    start_year = 1960
    end_year = max(observations.frame["date"])
    realizations = evaluate_temporal_predictions(
        tracers,
        lpm_list,
        start_year,
        end_year,
    )

    # Starting without a date grid lets validated outer merges construct the
    # deterministic union produced by every tracer and realization.
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
            observations,
            summarize_temporal_realizations(realizations),
        )

    for i, realization in enumerate(realizations, start=1):
        series_by_tracer = normalize_series(realization)
        merged_all_models = merge_model_into_table(
            merged_all_models, series_by_tracer, model_id=i
        )

    if display.figure:
        fig.tight_layout()
        finalize_figure(
            fig,
            display.figure_path("concentration_times.png", method=method),
            close=display.figure_close,
        )

    outfile_data = Path(display.directory) / method / "concentrations_all_models.txt"
    save_concentrations_table(merged_all_models, outfile_data)

    save_distributions_tables(pdf, lpm_statistics, Path(display.directory) / method)


__all__ = ["export_calibrated_chronicles", "export_concentration_chronicles"]
