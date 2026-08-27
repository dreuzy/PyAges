# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Plot helpers for concentration time series.

Purpose
-------
Provide small, reusable plotting utilities for tracer chronicle displays.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

import numpy as np
import pandas as pd

from pyages.concentrations.utils.tables import to_cv_dict


def _pretty_tracer_name(name: str) -> str:
    lower = name.lower()
    if lower.startswith("cfc"):
        return name.upper()
    if lower == "sf6":
        return "SF6"
    return name


def plot_tracer_series(
    cv_dict: Mapping[str, pd.DataFrame],
    axs,
    graph_type: Literal["scatter", "line"] = "scatter",
    title_prefix: str = "",
    label_prefix: str = "",
) -> list:
    """
    Plot tracer series (date vs concentration) on a grid of axes.

    Parameters
    ----------
    cv_dict : dict
        Dict {tracer: DataFrame(date, concentration, ...)}.
    axs : array-like of matplotlib axes
        Axes grid or list of axes.
    graph_type : str, optional
        "scatter" (default) or "line".
    title_prefix : str, optional
        Optional prefix for subplot titles.
    label_prefix : str, optional
        Optional prefix for legend labels.

    Returns
    -------
    list
        Matplotlib artists, one for each tracer.
    """
    if graph_type not in {"scatter", "line"}:
        raise ValueError("graph_type must be either 'scatter' or 'line'")
    series = to_cv_dict(cv_dict)
    flat_axes = np.atleast_1d(axs).flatten()
    if len(flat_axes) < len(series):
        raise ValueError(
            f"Not enough axes for tracer series: {len(series)} required, "
            f"{len(flat_axes)} provided"
        )

    artists = []
    for idx, (tracer, df) in enumerate(series.items()):
        ax = flat_axes[idx]
        title = f"{title_prefix}{tracer}" if title_prefix else tracer
        ax.set_title(title)
        date = df["date"]
        conc = df["concentration"]
        label = f"{label_prefix}{tracer}" if label_prefix else tracer
        if graph_type == "scatter":
            artists.append(ax.scatter(date, conc, label=label))
        else:
            (artist,) = ax.plot(date, conc, label=label)
            artists.append(artist)
    return artists


def plot_concentration_chronicles(
    fig,
    axs,
    conc_data,
    tracers,
    lpm_list: Sequence,
    start_year: float,
    end_year: float,
    plot_stride: int = 1,
):
    """
    Plot observed data and model chronicle curves on shared axes.

    Parameters
    ----------
    fig : matplotlib figure
        Target figure.
    axs : array-like of matplotlib axes
        Axes grid to draw into.
    conc_data : ConcentrationTime
        Observed concentration data.
    tracers : ConvolutionTracers
        Tracers used for convolution.
    lpm_list : list
        List of sampled LPMs to plot.
    start_year : float
        Start year for convolution.
    end_year : float
        End year for convolution.
    plot_stride : int, optional
        Plot every N-th model to reduce clutter.
    """
    if isinstance(plot_stride, bool) or not isinstance(plot_stride, int):
        raise TypeError("plot_stride must be an integer")
    if plot_stride < 1:
        raise ValueError("plot_stride must be at least 1")
    conc_data.display(fig, axs, graph_type="scatter")
    for i, lpm in enumerate(lpm_list, start=1):
        concentrations = tracers.convolve_date_range(lpm, start_year, end_year)
        conc_model = type(conc_data)(cv=concentrations)
        if plot_stride <= 1 or i % plot_stride == 0:
            conc_model.display(fig, axs, graph_type="line")


def plot_concentration_chronicles_summary(
    axs,
    craw,
    tracers,
    lpm_list: Sequence,
    start_year: float,
    end_year: float,
):
    """
    Plot observations together with posterior median and uncertainty bands.

    Parameters
    ----------
    axs : array-like of matplotlib axes
        Axes grid to draw into.
    craw : Concentrations
        Observed concentrations in long format.
    tracers : ConvolutionTracers
        Tracers used for convolution.
    lpm_list : list
        Sampled calibrated LPMs.
    start_year : float
        Start year for model chronicle computation.
    end_year : float
        End year for model chronicle computation.
    """
    axs = np.atleast_1d(axs).flatten()
    tracer_names = list(dict.fromkeys(craw.cv["element"].tolist()))

    predictions: dict[str, list[np.ndarray]] = {}
    prediction_dates: dict[str, np.ndarray] = {}
    for lpm in lpm_list:
        concentration_dict = tracers.convolve_date_range(lpm, start_year, end_year)
        for tracer_name, tracer_df in concentration_dict.items():
            ordered = tracer_df.sort_values("date")
            dates = ordered["date"].to_numpy(dtype=float)
            existing_dates = prediction_dates.get(tracer_name)
            if existing_dates is not None and (
                existing_dates.shape != dates.shape
                or not np.allclose(existing_dates, dates, rtol=0.0, atol=1e-10)
            ):
                raise ValueError(
                    f"Model realizations use inconsistent date grids for {tracer_name!r}"
                )
            prediction_dates[tracer_name] = dates
            predictions.setdefault(tracer_name, []).append(
                ordered["concentration"].to_numpy(dtype=float)
            )

    for idx, tracer_name in enumerate(tracer_names):
        if idx >= len(axs):
            break
        ax = axs[idx]
        observed = craw.cv[craw.cv["element"] == tracer_name].sort_values("date")
        unit = (
            observed["unit"].iloc[0]
            if "unit" in observed.columns and not observed.empty
            else None
        )

        if tracer_name in predictions:
            pred_array = np.vstack(predictions[tracer_name])
            pred_dates = prediction_dates[tracer_name]
            q10, q25, q50, q75, q90 = np.quantile(
                pred_array,
                [0.10, 0.25, 0.50, 0.75, 0.90],
                axis=0,
            )
            ax.fill_between(
                pred_dates, q10, q90, color="#c6dbef", alpha=0.8, label="90% interval"
            )
            ax.fill_between(
                pred_dates, q25, q75, color="#6baed6", alpha=0.75, label="50% interval"
            )
            ax.plot(
                pred_dates, q50, color="#08519c", linewidth=2.2, label="Median model"
            )

        has_error = "error" in observed.columns and np.any(
            pd.to_numeric(observed["error"], errors="coerce") > 0
        )
        yerr = observed["error"] if has_error else None
        ax.errorbar(
            observed["date"],
            observed["concentration"],
            yerr=yerr,
            fmt="o",
            color="#111111",
            ecolor="#4d4d4d",
            elinewidth=1.1,
            capsize=2,
            ms=5,
            label="Observations",
        )

        pretty_name = _pretty_tracer_name(tracer_name)
        ax.set_title(pretty_name)
        ax.set_xlabel("Year")
        ylabel = f"{pretty_name} [{unit}]" if unit else pretty_name
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25, linestyle="--")

    for ax in axs[len(tracer_names) :]:
        ax.remove()
