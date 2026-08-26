"""Observation overview figures."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from pyage.workflows.plots.common import (
    MEDIAN_COLOR,
    SINGLE_DATE_HIGHLIGHT_COLOR,
    _axis_label,
    _pretty_tracer_name,
    _save_figure,
    apply_example_style,
)


def plot_observations_overview(
    cdata,
    filename: str | Path | None = None,
    title: str = "Observed concentrations",
    highlight_dates: list[float] | None = None,
    highlight_label: str = "Single-date interpretation",
    highlight_tolerance: float = 0.02,
):
    """
    Plot observation-only panels for each tracer.
    """
    apply_example_style()
    df = cdata.cv.copy()
    tracers = list(dict.fromkeys(df["element"].tolist()))
    ncols = 2 if len(tracers) == 4 else min(3, max(len(tracers), 1))
    nrows = ceil(max(len(tracers), 1) / ncols)
    fig, axs = plt.subplots(
        nrows, ncols, figsize=(6.2 * ncols, 3.8 * nrows), squeeze=False
    )
    highlight_array = np.asarray(highlight_dates or [], dtype=float)
    highlighted_any = False

    for ax, tracer in zip(axs.flatten(), tracers, strict=False):
        tracer_df = df[df["element"] == tracer].sort_values("date")
        has_error = "error" in tracer_df.columns and np.any(
            pd.to_numeric(tracer_df["error"], errors="coerce") > 0
        )
        yerr = tracer_df["error"] if has_error else None
        ax.errorbar(
            tracer_df["date"],
            tracer_df["concentration"],
            yerr=yerr,
            fmt="o",
            ms=5,
            color=MEDIAN_COLOR,
            ecolor="#9ecae1",
            elinewidth=1.2,
            capsize=2,
        )
        if highlight_array.size:
            dates = pd.to_numeric(tracer_df["date"], errors="coerce").to_numpy(
                dtype=float
            )
            highlight_mask = np.any(
                np.isclose(
                    dates[:, None],
                    highlight_array[None, :],
                    atol=float(highlight_tolerance),
                    rtol=0.0,
                ),
                axis=1,
            )
            if highlight_mask.any():
                highlighted_any = True
                highlight_df = tracer_df.loc[highlight_mask]
                highlight_yerr = yerr.loc[highlight_df.index] if has_error else None
                ax.errorbar(
                    highlight_df["date"],
                    highlight_df["concentration"],
                    yerr=highlight_yerr,
                    fmt="o",
                    ms=6.5,
                    color=SINGLE_DATE_HIGHLIGHT_COLOR,
                    ecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                    elinewidth=1.4,
                    capsize=2,
                    markeredgecolor="white",
                    markeredgewidth=0.7,
                    zorder=4,
                )
        unit = (
            tracer_df["unit"].iloc[0]
            if "unit" in tracer_df.columns and not tracer_df.empty
            else None
        )
        ax.set_title(_pretty_tracer_name(tracer))
        ax.set_xlabel("Year")
        ax.set_ylabel(_axis_label(tracer, unit))

    for ax in axs.flatten()[len(tracers) :]:
        ax.remove()

    if highlighted_any:
        fig.legend(
            handles=[
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markersize=6,
                    markerfacecolor=MEDIAN_COLOR,
                    markeredgecolor=MEDIAN_COLOR,
                    label="Temporal observations",
                ),
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markersize=7,
                    markerfacecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                    markeredgecolor="white",
                    label=highlight_label,
                ),
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=2,
        )
    fig.suptitle(title, fontsize=15, y=1.08 if highlighted_any else 1.04)
    fig.tight_layout(rect=(0, 0, 1, 0.91 if highlighted_any else 0.96))
    return _save_figure(fig, filename)


__all__ = ["plot_observations_overview"]
