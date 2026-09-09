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


def _column(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return one unambiguous column from a derived figure table."""
    column = frame[name]
    if not isinstance(column, pd.Series):
        raise ValueError(f"Expected exactly one {name!r} column")
    return column


def _matching_rows(frame: pd.DataFrame, name: str, value: object) -> pd.DataFrame:
    """Select rows by one column while preserving the DataFrame contract."""
    selected = frame.loc[_column(frame, name).eq(value)]
    if not isinstance(selected, pd.DataFrame):
        raise TypeError("Boolean row selection must produce a DataFrame")
    return selected


def _masked_rows(frame: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Apply an already computed row mask and retain a DataFrame."""
    selected = frame.loc[mask]
    if not isinstance(selected, pd.DataFrame):
        raise TypeError("Boolean row selection must produce a DataFrame")
    return selected


def plot_figure4(frame: pd.DataFrame, figures: Path) -> list[Path]:
    """Compare conditioned and unconstrained median transit times."""
    if frame.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True, constrained_layout=True)
    for ax, well in zip(axes, ("F11", "F09"), strict=False):
        subset = _matching_rows(frame, "well", well)
        for mode, color, label in (
            ("successive_with_prior", CONDITIONED, "Conditioned"),
            ("successive", UNCONSTRAINED, "Unconstrained"),
        ):
            data = _matching_rows(subset, "mode", mode).sort_values(by="date")
            ax.errorbar(
                _column(data, "date").to_numpy(dtype=float),
                _column(data, "p50_mean").to_numpy(dtype=float),
                yerr=_column(data, "p50_std").to_numpy(dtype=float),
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
        subset = _matching_rows(frame, "well", well)
        for model, label in (
            ("exp_shifted", "Shifted exponential"),
            ("ig_shifted", "Shifted inverse Gaussian"),
        ):
            data = _matching_rows(subset, "lpm", model).sort_values(by="date")
            ax.errorbar(
                _column(data, "date").to_numpy(dtype=float),
                _column(data, "p50_mean").to_numpy(dtype=float),
                yerr=_column(data, "p50_std").to_numpy(dtype=float),
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
    present = set(_column(frame, "well").dropna())
    required = set(WELL_COLORS)
    if not allow_partial and present != required:
        return []
    p50_mean = _column(frame, "p50_mean")
    low = _masked_rows(frame, p50_mean.lt(25))
    high = _masked_rows(frame, p50_mean.ge(25))
    broken = not low.empty and not high.empty
    bottom = None
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
        data = _matching_rows(frame, "well", well).sort_values(by="date")
        if data.empty:
            continue
        for ax in axes:
            ax.errorbar(
                _column(data, "date").to_numpy(dtype=float),
                _column(data, "p50_mean").to_numpy(dtype=float),
                yerr=_column(data, "p50_std").to_numpy(dtype=float),
                fmt="o--",
                capsize=3,
                color=color,
                label=well,
            )
    if bottom is not None:
        high_values = _column(high, "p50_mean").to_numpy(dtype=float)
        low_values = _column(low, "p50_mean").to_numpy(dtype=float)
        top.set_ylim(
            max(25, float(high_values.min()) - 8), float(high_values.max()) + 8
        )
        bottom.set_ylim(0, max(12, float(low_values.max()) + 3))
        top.spines.bottom.set_visible(False)
        bottom.spines.top.set_visible(False)
        top.tick_params(labeltop=False, bottom=False)
        bottom.xaxis.tick_bottom()
        break_marks = {
            "marker": ((-1, -0.5), (1, 0.5)),
            "markersize": 8,
            "linestyle": "none",
            "color": "k",
            "mec": "k",
            "mew": 1,
            "clip_on": False,
        }
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
        subset = _matching_rows(frame, "well", well)
        grouped = subset.groupby(["relative_error", "lpm"], as_index=False).agg(
            p50_mean=("p50_mean", "mean")
        )
        for model, data in grouped.groupby("lpm"):
            if not isinstance(data, pd.DataFrame):
                raise TypeError("Grouped figure rows must be a DataFrame")
            ax.plot(
                100 * _column(data, "relative_error").to_numpy(dtype=float),
                _column(data, "p50_mean").to_numpy(dtype=float),
                "o-",
                label=str(model),
            )
        ax.set_title(well, loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    axes[-1].set_xlabel("Relative error (%)")
    fig.supylabel("Mean posterior median transit time (years)")
    return export_figure(fig, figures, "FigureA1")


__all__ = ["plot_figure4", "plot_figure5", "plot_figure6", "plot_figure_a1"]
