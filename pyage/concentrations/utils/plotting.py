# -*- coding: utf-8 -*-
"""
Plot helpers for concentration time series.

Purpose
-------
Provide small, reusable plotting utilities for tracer chronicle displays.
"""

from typing import Dict

import numpy as np
import pandas as pd


def plot_tracer_series(
    cv_dict: Dict[str, pd.DataFrame],
    axs,
    graph_type: str = "scatter",
    title_prefix: str = "",
    label_prefix: str = "",
):
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
    """
    axs = np.atleast_1d(axs).flatten()
    for idx, (tracer, df) in enumerate(cv_dict.items()):
        if idx >= len(axs):
            break
        ax = axs[idx]
        title = f"{title_prefix}{tracer}" if title_prefix else tracer
        ax.set_title(title)
        date = df["date"]
        conc = df["concentration"]
        label = f"{label_prefix}{tracer}" if label_prefix else tracer
        if graph_type == "scatter":
            ax.scatter(date, conc, label=label)
        else:
            ax.plot(date, conc, label=label)


def plot_concentration_chronicles(
    fig,
    axs,
    conc_data,
    tracers,
    lpm_list,
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
    conc_data.display(fig, axs, graph_type="scatter")
    for i, lpm in enumerate(lpm_list, start=1):
        concentrations = tracers.convolution_date_range(lpm, start_year, end_year)
        conc_model = type(conc_data)(cv=concentrations)
        if plot_stride <= 1 or i % plot_stride == 0:
            conc_model.display(fig, axs, graph_type="line")
