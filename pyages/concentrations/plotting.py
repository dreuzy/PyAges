# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Render concentration chronicles on caller-owned Matplotlib axes.

Table normalization and posterior-quantile computation stay in their dedicated
modules. Keeping those operations outside rendering loops gives workflow
figures and contributor plots the same date-alignment and validation contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from pyages.concentrations.schema import CONCENTRATION_COLUMN
from pyages.concentrations.series import ConcentrationSeries, normalize_series
from pyages.concentrations.temporal import TemporalPredictionSummary

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.collections import PathCollection


def _pretty_tracer_name(name: str) -> str:
    lower = name.lower()
    if lower.startswith("cfc"):
        return name.upper()
    if lower == "sf6":
        return "SF6"
    return name


def _require_axes(axs, count: int, *, context: str) -> np.ndarray:
    """Return flattened axes or reject a layout that would omit tracers."""
    flat_axes = np.atleast_1d(axs).flatten()
    if len(flat_axes) < count:
        raise ValueError(
            f"Not enough axes for {context}: {count} required, "
            f"{len(flat_axes)} provided"
        )
    return flat_axes


def plot_concentration_pair(
    frame: pd.DataFrame,
    i1: int,
    i2: int,
    *,
    label_x: str | None = None,
    label_y: str | None = None,
    ax: Axes | None = None,
) -> PathCollection:
    """Plot two concentration rows and return the Matplotlib artist."""
    if (
        isinstance(i1, bool)
        or isinstance(i2, bool)
        or not isinstance(i1, int)
        or not isinstance(i2, int)
        or i1 < 0
        or i2 < 0
        or i1 >= len(frame)
        or i2 >= len(frame)
    ):
        raise IndexError("Index out of range for concentration plot.")
    if ax is None:
        # Import pyplot only for the implicit-axis convenience path. Importing
        # the concentration data API itself must not initialize Matplotlib.
        import matplotlib.pyplot as plt

        ax = plt.gca()
    artist = ax.scatter(
        frame[CONCENTRATION_COLUMN].iloc[i1],
        frame[CONCENTRATION_COLUMN].iloc[i2],
        marker="o",
        c="r",
        s=150,
    )
    if label_x:
        ax.set_xlabel(label_x)
    if label_y:
        ax.set_ylabel(label_y)
    return artist


def plot_tracer_series(
    series_by_tracer: Mapping[str, pd.DataFrame],
    axs,
    graph_type: Literal["scatter", "line"] = "scatter",
    title_prefix: str = "",
    label_prefix: str = "",
) -> list:
    """
    Plot tracer series (date vs concentration) on a grid of axes.

    Parameters
    ----------
    series_by_tracer : dict
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
    series = normalize_series(series_by_tracer)
    flat_axes = _require_axes(axs, len(series), context="tracer series")

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
    chronicle,
    realizations: Sequence[ConcentrationSeries],
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
    chronicle : ConcentrationChronicle
        Observed concentration data.
    realizations : sequence of mappings
        Precomputed tracer series for each selected model realization.
    plot_stride : int, optional
        Plot every N-th model to reduce clutter.
    """
    if isinstance(plot_stride, bool) or not isinstance(plot_stride, int):
        raise TypeError("plot_stride must be an integer")
    if plot_stride < 1:
        raise ValueError("plot_stride must be at least 1")
    chronicle.plot(fig, axs, graph_type="scatter")
    for index, realization in enumerate(realizations, start=1):
        if plot_stride <= 1 or index % plot_stride == 0:
            type(chronicle)(series=realization).plot(fig, axs, graph_type="line")


def plot_concentration_chronicles_summary(
    axs,
    observations,
    summaries: Mapping[str, TemporalPredictionSummary],
):
    """
    Plot observations together with posterior median and uncertainty bands.

    Parameters
    ----------
    axs : array-like of matplotlib axes
        Axes grid to draw into.
    observations : Concentrations
        Observed concentrations in long format.
    summaries : mapping
        Validated posterior summaries keyed by tracer name.
    """
    tracer_names = observations.unique_tracer_names()
    axs = _require_axes(axs, len(tracer_names), context="chronicle summary")
    expected = set(tracer_names)
    actual = set(summaries)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            "Temporal summaries do not match observation tracers: "
            f"missing={missing}, extra={extra}"
        )

    for idx, tracer_name in enumerate(tracer_names):
        ax = axs[idx]
        observed = observations.frame[
            observations.frame["element"] == tracer_name
        ].sort_values("date")
        unit = (
            observed["unit"].iloc[0]
            if "unit" in observed.columns and not observed.empty
            else None
        )

        summary = summaries[tracer_name]
        ax.fill_between(
            summary.dates,
            summary.q10,
            summary.q90,
            color="#c6dbef",
            alpha=0.8,
            label="90% interval",
        )
        ax.fill_between(
            summary.dates,
            summary.q25,
            summary.q75,
            color="#6baed6",
            alpha=0.75,
            label="50% interval",
        )
        ax.plot(
            summary.dates,
            summary.median,
            color="#08519c",
            linewidth=2.2,
            label="Median model",
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


__all__ = [
    "plot_concentration_chronicles",
    "plot_concentration_chronicles_summary",
    "plot_concentration_pair",
    "plot_tracer_series",
]
