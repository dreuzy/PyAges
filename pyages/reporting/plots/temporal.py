# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file compares calibrated tracer histories with dated observations.

"""Plot temporal predictions and their posterior uncertainty by tracer.

Calibrated parameter samples are converted back into LPM realizations and
convolved over a common date interval. Their predicted histories are summarized
as medians and uncertainty bands, then placed behind the measured concentrations
and available error bars in one panel per tracer.

The summary view shows nested 50% and 90% intervals for one calibration result.
The comparison view overlays the median and 90% interval from several posterior
sources and can emphasize selected observation dates. This module assembles and
saves figures; validation and quantile calculation remain in the concentration
and convolution layers.
"""

from __future__ import annotations

from math import ceil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from pyages.concentrations.temporal import (
    TemporalPredictionSummary,
    summarize_temporal_predictions,
)
from pyages.convolution import ConvolutionTracers
from pyages.lpm.factory import build_lpm
from pyages.lpm.samples.table import LpmSampleTable
from pyages.reporting.plots._common import (
    INTERVAL_50_COLOR,
    INTERVAL_90_COLOR,
    MEDIAN_COLOR,
    OBSERVED_COLOR,
    SINGLE_DATE_HIGHLIGHT_COLOR,
    _axis_label,
    _pretty_tracer_name,
    _save_figure,
    apply_example_style,
)

OVERLAY_STYLES = (
    {
        "band": "#c6dbef",
        "line": "#08519c",
        "band_label": "Transient 90% interval",
        "line_label": "Transient median",
    },
    {
        "band": "#fdd0a2",
        "line": "#d94801",
        "band_label": "Single-date 90% interval",
        "line_label": "Single-date median",
    },
    {
        "band": "#d9d9d9",
        "line": "#636363",
        "band_label": "Comparison 90% interval",
        "line_label": "Comparison median",
    },
)


def _posterior_predictions(
    posterior_frames: dict[str, pd.DataFrame],
    lpm_name: str,
    lpm_directory: str | Path,
    tracers,
    start_year: float,
    end_year: float,
    lpm_number: int,
) -> dict[str, dict[str, TemporalPredictionSummary]]:
    """Convert posterior tables into summarized tracer histories.

    Each table is attached to a fresh LPM template, reduced to a representative
    set of calibrated models, and convolved over the requested date interval.
    The returned quantiles can then be plotted without retaining every modeled
    trajectory in the figure-building code.
    """
    predictions = {}
    for label, frame in posterior_frames.items():
        if frame.empty:
            continue
        template = build_lpm(lpm_name, directory_lpm=str(lpm_directory))
        distribution = LpmSampleTable(template, c_names=[])
        distribution.replace_frame(frame)
        lpms, _, _ = distribution.select(
            count=lpm_number,
            resolution=1000,
        )
        predictions[label] = summarize_temporal_predictions(
            tracers,
            lpms,
            start_year,
            end_year,
        )
    return predictions


def _comparison_legend(highlighted: bool, highlight_label: str) -> list:
    """Build observation legend entries shared by all temporal panels."""
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color="#111111",
            markerfacecolor="#111111",
            markeredgecolor="#111111",
            markersize=6,
            label="Observations",
        )
    ]
    if highlighted:
        handles.append(
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color=SINGLE_DATE_HIGHLIGHT_COLOR,
                markerfacecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                markeredgecolor="white",
                markersize=7,
                label=highlight_label,
            )
        )
    return handles


def _plot_prediction_intervals(axs, tracer_names, predictions, legend_handles) -> None:
    """Overlay each source's 90% interval and median on every tracer panel.

    A source keeps the same band and line colors across tracers so comparisons
    remain meaningful when the reader moves between panels.
    """
    for source_index, source in enumerate(predictions.values()):
        style = OVERLAY_STYLES[min(source_index, len(OVERLAY_STYLES) - 1)]
        legend_handles.extend(
            [
                Patch(
                    facecolor=style["band"],
                    edgecolor="none",
                    alpha=0.75,
                    label=style["band_label"],
                ),
                Line2D(
                    [],
                    [],
                    color=style["line"],
                    linewidth=2.4,
                    label=style["line_label"],
                ),
            ]
        )
        for ax, tracer_name in zip(axs.flatten(), tracer_names, strict=False):
            if tracer_name not in source:
                continue
            summary = source[tracer_name]
            ax.fill_between(
                summary.dates,
                summary.q10,
                summary.q90,
                color=style["band"],
                alpha=0.55 if source_index else 0.75,
            )
            ax.plot(
                summary.dates,
                summary.median,
                color=style["line"],
                linewidth=2.3,
            )


def _plot_observed_temporal_panel(
    ax,
    observed: pd.DataFrame,
    tracer_name: str,
    highlight_dates: np.ndarray,
    highlight_tolerance: float,
) -> bool:
    """Plot one tracer's observations and optionally emphasize selected dates.

    Dates are matched with an absolute tolerance because measurements and user
    selections may have small floating-point differences.  The return value
    tells the caller whether the highlight deserves an entry in the legend.
    """
    unit = (
        observed["unit"].iloc[0] if "unit" in observed and not observed.empty else None
    )
    has_error = "error" in observed and np.any(
        pd.to_numeric(observed["error"], errors="coerce") > 0
    )
    error = observed["error"] if has_error else None
    ax.errorbar(
        observed["date"],
        observed["concentration"],
        yerr=error,
        fmt="o",
        color="#111111",
        ecolor="#4d4d4d",
        elinewidth=1.1,
        capsize=2,
        ms=5,
        zorder=5,
    )
    highlighted = False
    if highlight_dates.size:
        dates = pd.to_numeric(observed["date"], errors="coerce").to_numpy(dtype=float)
        mask = np.any(
            np.isclose(
                dates[:, None],
                highlight_dates[None, :],
                atol=float(highlight_tolerance),
                rtol=0.0,
            ),
            axis=1,
        )
        if mask.any():
            highlighted = True
            selected = observed.loc[mask]
            selected_error = error.loc[selected.index] if has_error else None
            ax.errorbar(
                selected["date"],
                selected["concentration"],
                yerr=selected_error,
                fmt="o",
                color=SINGLE_DATE_HIGHLIGHT_COLOR,
                ecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                elinewidth=1.5,
                capsize=2,
                ms=6.5,
                markeredgecolor="white",
                markeredgewidth=0.8,
                zorder=6,
            )
    ax.set_title("")
    ax.set_xlabel("Year", fontsize=18)
    ax.set_ylabel(_axis_label(tracer_name, unit), fontsize=18)
    ax.tick_params(axis="both", labelsize=16)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    return highlighted


def plot_temporal_fit_comparison(
    observations,
    posterior_frames: dict[str, pd.DataFrame],
    lpm_name: str,
    lpm_directory: str | Path,
    lpm_number: int = 40,
    filename: str | Path | None = None,
    title: str | None = None,
    start_year: float = 1960,
    highlight_dates: list[float] | None = None,
    highlight_label: str = "Single-date observation",
    highlight_tolerance: float = 0.02,
):
    """Compare tracer histories predicted by several posterior distributions.

    One panel is created per observed tracer.  For each named posterior source,
    a representative set of calibrated LPMs is convolved through time and
    summarized by its median and 90% interval.  Dated measurements are drawn on
    top, with optional dates highlighted consistently across all panels.
    """
    apply_example_style()
    tracer_names = observations.unique_tracer_names()
    ncols = len(tracer_names) if len(tracer_names) <= 3 else 2
    nrows = ceil(max(len(tracer_names), 1) / ncols)
    fig, axs = plt.subplots(
        nrows, ncols, figsize=(6.5 * ncols, 4.2 * nrows), squeeze=False
    )
    highlight_array = np.asarray(highlight_dates or [], dtype=float)
    highlighted_any = False

    # All sources use the same tracer definitions and time window, so their
    # uncertainty bands remain directly comparable.
    end_year = float(observations.frame["date"].max())
    tracers = ConvolutionTracers(
        names=observations.unique_tracer_names(),
        date=end_year,
    )
    tracers.validate_observation_units(observations)

    predictions = _posterior_predictions(
        posterior_frames,
        lpm_name,
        lpm_directory,
        tracers,
        start_year,
        end_year,
        lpm_number,
    )
    legend_handles = _comparison_legend(bool(highlight_array.size), highlight_label)
    _plot_prediction_intervals(axs, tracer_names, predictions, legend_handles)

    # Observations are plotted last so they remain visible above uncertainty
    # bands, including when several posterior sources overlap.
    for ax, tracer_name in zip(axs.flatten(), tracer_names, strict=False):
        observed = observations.frame[
            observations.frame["element"] == tracer_name
        ].sort_values("date")
        highlighted_any |= _plot_observed_temporal_panel(
            ax,
            observed,
            tracer_name,
            highlight_array,
            highlight_tolerance,
        )

    for ax in axs.flatten()[len(tracer_names) :]:
        ax.remove()

    legend_items = [
        handle
        for handle in legend_handles
        if highlighted_any or handle.get_label() != highlight_label
    ]

    fig.legend(
        legend_items,
        [handle.get_label() for handle in legend_items],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=min(len(legend_items), 3),
        fontsize=18,
        frameon=False,
    )
    if title:
        fig.suptitle(title, fontsize=15, y=1.08)
        fig.tight_layout(rect=(0, 0, 1, 0.90))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save_figure(fig, filename)


def plot_temporal_fit_summary(
    observations,
    lpm_results,
    lpm_number: int,
    filename: str | Path | None = None,
    title: str | None = None,
    start_year: float = 1960,
):
    """Summarize one calibrated result as modeled tracer histories.

    A representative set of calibrated LPMs is propagated over time for every
    observed tracer.  Each panel shows the median prediction, central 50% and
    90% intervals, and dated observations with their available measurement
    errors.  The nested bands separate typical variation from wider uncertainty.
    """
    apply_example_style()
    end_year = float(observations.frame["date"].max())
    tracers = ConvolutionTracers(
        names=observations.unique_tracer_names(),
        date=end_year,
    )
    tracers.validate_observation_units(observations)
    lpm_list, _, _ = lpm_results.select(
        count=lpm_number,
        resolution=1000,
    )
    if not lpm_list:
        raise ValueError("No calibrated LPMs available to build temporal fit figure.")

    # Summarize trajectories before plotting so the panels depend on a small,
    # explicit set of quantiles instead of individual model curves.
    summaries = summarize_temporal_predictions(
        tracers,
        lpm_list,
        start_year,
        end_year,
    )

    tracer_names = observations.unique_tracer_names()
    ncols = min(2, max(len(tracer_names), 1))
    nrows = ceil(max(len(tracer_names), 1) / ncols)
    fig, axs = plt.subplots(
        nrows, ncols, figsize=(6.3 * ncols, 4.0 * nrows), squeeze=False
    )

    legend_handles = []
    legend_labels = []

    for ax, tracer_name in zip(axs.flatten(), tracer_names, strict=False):
        observed = observations.frame[
            observations.frame["element"] == tracer_name
        ].sort_values("date")
        unit = (
            observed["unit"].iloc[0]
            if "unit" in observed.columns and not observed.empty
            else None
        )

        summary = summaries[tracer_name]

        # Draw the wider band first so the central interval and median remain
        # visible as progressively more precise summaries.
        band90 = ax.fill_between(
            summary.dates,
            summary.q10,
            summary.q90,
            color=INTERVAL_90_COLOR,
            alpha=0.8,
        )
        band50 = ax.fill_between(
            summary.dates,
            summary.q25,
            summary.q75,
            color=INTERVAL_50_COLOR,
            alpha=0.75,
        )
        (median_line,) = ax.plot(
            summary.dates,
            summary.median,
            color=MEDIAN_COLOR,
            linewidth=2.2,
        )

        has_error = "error" in observed.columns and np.any(
            pd.to_numeric(observed["error"], errors="coerce") > 0
        )
        error = observed["error"] if has_error else None
        obs = ax.errorbar(
            observed["date"],
            observed["concentration"],
            yerr=error,
            fmt="o",
            color=OBSERVED_COLOR,
            ecolor="#4d4d4d",
            elinewidth=1.1,
            capsize=2,
            ms=5,
        )

        ax.set_title(_pretty_tracer_name(tracer_name))
        ax.set_xlabel("Year")
        ax.set_ylabel(_axis_label(tracer_name, unit))

        if not legend_handles:
            legend_handles = [obs, median_line, band50, band90]
            legend_labels = [
                "Observations",
                "Median model",
                "50% interval",
                "90% interval",
            ]

    for ax in axs.flatten()[len(tracer_names) :]:
        ax.remove()

    if legend_handles:
        fig.legend(legend_handles, legend_labels, loc="upper center", ncol=4)
        fig.subplots_adjust(top=0.82)
    fig.suptitle(title or "Temporal fit summary", fontsize=15, y=1.02)
    fig.tight_layout()
    return _save_figure(fig, filename)


__all__ = ["plot_temporal_fit_comparison", "plot_temporal_fit_summary"]
