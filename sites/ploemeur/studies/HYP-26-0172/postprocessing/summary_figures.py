# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Render HYP-26-0172 summary figures from declared derived CSV tables.

Every function receives an in-memory table whose columns already encode the
study coordinates. These builders never search native workflow directories;
that separation makes publication figures reproducible from durable derived
products alone.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .export import export_figure
from .style import CONDITIONED, MODEL_COLORS, UNCONSTRAINED, WELL_COLORS


def plot_figure4(frame: pd.DataFrame, figures: Path) -> list[Path]:
    """Compare conditioned and unconstrained median transit times."""
    if frame.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True, constrained_layout=True)
    for ax, well in zip(axes, ("F11", "F09"), strict=False):
        subset = frame[frame["well"].eq(well)]
        for mode, color, label in (
            ("successive_with_prior", CONDITIONED, "Conditioned"),
            ("successive", UNCONSTRAINED, "Unconstrained"),
        ):
            data = subset[subset["mode"].eq(mode)].sort_values("date")
            ax.errorbar(
                data["date"],
                data["p50_mean"],
                yerr=data["p50_std"],
                fmt="o",
                capsize=3,
                color=color,
                label=label,
            )
        ax.set_title(well, loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    axes[-1].set_xlabel("Date")
    fig.supylabel("Median transit time (years)")
    return export_figure(fig, figures, "Figure4")


def plot_figure5(frame: pd.DataFrame, figures: Path) -> list[Path]:
    """Compare shifted-exponential and shifted-inverse-Gaussian results."""
    if frame.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True, constrained_layout=True)
    for ax, well in zip(axes, ("F11", "F09"), strict=False):
        subset = frame[frame["well"].eq(well)]
        for model, label in (
            ("exp_shifted", "Shifted exponential"),
            ("ig_shifted", "Shifted inverse Gaussian"),
        ):
            data = subset[subset["lpm"].eq(model)].sort_values("date")
            ax.errorbar(
                data["date"],
                data["p50_mean"],
                yerr=data["p50_std"],
                fmt="o--",
                capsize=3,
                color=MODEL_COLORS[model],
                label=label,
            )
        ax.set_title(well, loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False)
    axes[-1].set_xlabel("Sampling year")
    fig.supylabel("Median transit time (years)")
    return export_figure(fig, figures, "Figure5")


def plot_figure6(
    frame: pd.DataFrame, figures: Path, allow_partial: bool = False
) -> list[Path]:
    """Compare five wells, using a broken axis only when ranges require it."""
    if frame.empty:
        return []
    frame = frame.copy()
    present = set(frame["well"].dropna())
    required = set(WELL_COLORS)
    if not allow_partial and present != required:
        return []
    low = frame[frame["p50_mean"] < 25]
    high = frame[frame["p50_mean"] >= 25]
    broken = not low.empty and not high.empty
    if broken:
        fig, (top, bottom) = plt.subplots(
            2,
            1,
            sharex=True,
            figsize=(8, 5),
            gridspec_kw={"height_ratios": [4, 1], "hspace": 0.05},
        )
        axes = (top, bottom)
    else:
        fig, top = plt.subplots(figsize=(8, 5))
        axes = (top,)
    for well, color in WELL_COLORS.items():
        data = frame[frame["well"].eq(well)].sort_values("date")
        if data.empty:
            continue
        for ax in axes:
            ax.errorbar(
                data["date"],
                data["p50_mean"],
                yerr=data["p50_std"],
                fmt="o--",
                capsize=3,
                color=color,
                label=well,
            )
    if broken:
        top.set_ylim(max(25, high["p50_mean"].min() - 8), high["p50_mean"].max() + 8)
        bottom.set_ylim(0, max(12, low["p50_mean"].max() + 3))
        top.spines.bottom.set_visible(False)
        bottom.spines.top.set_visible(False)
        top.tick_params(labeltop=False, bottom=False)
        bottom.xaxis.tick_bottom()
        break_marks = dict(
            marker=[(-1, -0.5), (1, 0.5)],
            markersize=8,
            linestyle="none",
            color="k",
            mec="k",
            mew=1,
            clip_on=False,
        )
        top.plot([0, 1], [0, 0], transform=top.transAxes, **break_marks)
        bottom.plot([0, 1], [1, 1], transform=bottom.transAxes, **break_marks)
    top.set_title("Shifted Exponential | error=20%", fontweight="bold")
    top.legend(frameon=False, ncol=2)
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("Date")
    fig.supylabel("Median transit time (years)")
    return export_figure(fig, figures, "Figure6")


def plot_figure_a1(frame: pd.DataFrame, figures: Path) -> list[Path]:
    """Plot the sensitivity of median transit time to relative error."""
    if frame.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True, constrained_layout=True)
    for ax, well in zip(axes, ("F11", "F09"), strict=False):
        subset = frame[frame["well"].eq(well)]
        grouped = subset.groupby(["relative_error", "lpm"], as_index=False)[
            "p50_mean"
        ].mean()
        for model, data in grouped.groupby("lpm"):
            ax.plot(100 * data["relative_error"], data["p50_mean"], "o-", label=model)
        ax.set_title(well, loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    axes[-1].set_xlabel("Relative error (%)")
    fig.supylabel("Mean posterior median transit time (years)")
    return export_figure(fig, figures, "FigureA1")


__all__ = ["plot_figure4", "plot_figure5", "plot_figure6", "plot_figure_a1"]
