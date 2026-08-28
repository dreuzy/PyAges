# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Objective-landscape figures."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pyages.reporting.plots._common import (
    GRID_CMAP,
    OBSERVED_COLOR,
    _best_row,
    _ensure_frame,
    _method_color,
    _nearest_reference_objective_row,
    _save_figure,
    apply_example_style,
)


def _plot_summary_posterior(
    ax,
    posterior_results: dict[str, object],
    x_name: str,
    y_name: str,
    *,
    show_labels: bool,
) -> None:
    """Overlay posterior samples and best points on one summary axis."""
    for method_index, (method_name, result) in enumerate(posterior_results.items()):
        frame = _ensure_frame(result)
        color = _method_color(method_name, method_index)
        sample = frame[[x_name, y_name]].dropna()
        ax.scatter(
            sample[x_name],
            sample[y_name],
            s=18,
            color=color,
            alpha=0.15,
            linewidths=0,
            label=f"{method_name} posterior samples" if show_labels else None,
        )
        best = _best_row(frame)
        if best is not None:
            ax.scatter(
                best[x_name],
                best[y_name],
                marker="*",
                s=130,
                color=color,
                edgecolor="white",
                linewidth=0.8,
                label=f"{method_name} posterior best" if show_labels else None,
                zorder=5,
            )


def _plot_summary_objective_axis(
    ax,
    grid_frame: pd.DataFrame,
    best_grid: pd.Series,
    objective_column: str,
    x_name: str,
    posterior_results: dict[str, object],
    reference_params: dict[str, float] | None,
    reference_row: pd.Series | None,
    reference_label: str,
    *,
    show_labels: bool,
):
    """Plot a one-parameter objective summary."""
    scalar = ax.scatter(
        grid_frame[x_name],
        grid_frame[objective_column],
        c=grid_frame[objective_column],
        s=18,
        cmap=GRID_CMAP,
        alpha=0.55,
        edgecolors="none",
    )
    ax.scatter(
        best_grid[x_name],
        best_grid[objective_column],
        marker="*",
        s=160,
        color="white",
        edgecolor=OBSERVED_COLOR,
        linewidth=0.9,
        label="Best prior grid point" if show_labels else None,
        zorder=4,
    )
    _plot_summary_posterior(
        ax,
        posterior_results,
        x_name,
        "obj_function",
        show_labels=show_labels,
    )
    if reference_params and x_name in reference_params and reference_row is not None:
        ax.scatter(
            float(reference_params[x_name]),
            float(reference_row[objective_column]),
            marker="D",
            s=90,
            color=OBSERVED_COLOR,
            edgecolor="white",
            linewidth=0.8,
            label=reference_label if show_labels else None,
            zorder=6,
        )
    ax.set_xlabel(x_name)
    ax.set_ylabel("Objective function")
    return scalar


def _plot_summary_parameter_axis(
    ax,
    grid_frame: pd.DataFrame,
    best_grid: pd.Series,
    objective_column: str,
    x_name: str,
    y_name: str,
    posterior_results: dict[str, object],
    reference_params: dict[str, float] | None,
    reference_label: str,
    *,
    show_labels: bool,
):
    """Plot a two-parameter objective summary."""
    scalar = ax.scatter(
        grid_frame[x_name],
        grid_frame[y_name],
        c=grid_frame[objective_column],
        s=18,
        cmap=GRID_CMAP,
        alpha=0.55,
        edgecolors="none",
    )
    ax.scatter(
        best_grid[x_name],
        best_grid[y_name],
        marker="*",
        s=160,
        color="white",
        edgecolor=OBSERVED_COLOR,
        linewidth=0.9,
        label="Best prior grid point" if show_labels else None,
        zorder=4,
    )
    _plot_summary_posterior(
        ax,
        posterior_results,
        x_name,
        y_name,
        show_labels=show_labels,
    )
    if reference_params and {x_name, y_name}.issubset(reference_params):
        ax.scatter(
            float(reference_params[x_name]),
            float(reference_params[y_name]),
            marker="D",
            s=90,
            color=OBSERVED_COLOR,
            edgecolor="white",
            linewidth=0.8,
            label=reference_label if show_labels else None,
            zorder=6,
        )
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    return scalar


def plot_objective_summary(
    objective_frame: pd.DataFrame,
    posterior_results: dict[str, object],
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "Reference parameters",
    filename: str | Path | None = None,
    title: str = "Objective landscape and estimated parameters",
):
    """
    Plot pairwise parameter views colored by objective value.
    """
    apply_example_style()
    if not param_names:
        raise ValueError("At least one parameter is required.")
    objective_col = (
        "half_log_chi_square"
        if "half_log_chi_square" in objective_frame.columns
        else "obj_function"
    )
    if objective_col not in objective_frame.columns:
        raise ValueError(
            "Objective frame must contain 'half_log_chi_square' or 'obj_function'."
        )

    if len(param_names) == 1:
        pairs = [(param_names[0], objective_col)]
    else:
        pairs = list(combinations(param_names, 2))
    pairs = pairs[:3]

    ncols = len(pairs)
    fig_width = 5.6 * ncols + 1.4
    fig, axs = plt.subplots(1, ncols, figsize=(fig_width, 4.8), squeeze=False)
    axs = axs.flatten()

    grid_frame = objective_frame.copy()
    if len(grid_frame) > 8000:
        grid_frame = grid_frame.sample(8000, random_state=12345)
    best_grid = objective_frame.loc[
        pd.to_numeric(objective_frame[objective_col], errors="coerce").idxmin()
    ]
    nearest_reference_row = _nearest_reference_objective_row(
        objective_frame,
        reference_params,
        param_names,
    )
    scalar = None

    for ax_index, ((xname, yname), ax) in enumerate(zip(pairs, axs, strict=True)):
        if yname == objective_col:
            scalar = _plot_summary_objective_axis(
                ax,
                grid_frame,
                best_grid,
                objective_col,
                xname,
                posterior_results,
                reference_params,
                nearest_reference_row,
                reference_label,
                show_labels=ax_index == 0,
            )
        else:
            scalar = _plot_summary_parameter_axis(
                ax,
                grid_frame,
                best_grid,
                objective_col,
                xname,
                yname,
                posterior_results,
                reference_params,
                reference_label,
                show_labels=ax_index == 0,
            )
        ax.set_title(f"{xname} vs {yname if yname != objective_col else 'objective'}")

    if scalar is not None:
        plot_right = 0.80 if ncols == 1 else 0.84
        colorbar_left = 0.88 if ncols == 1 else 0.90
        fig.subplots_adjust(
            left=0.10, right=plot_right, bottom=0.12, top=0.77, wspace=0.28
        )
        cax = fig.add_axes([colorbar_left, 0.18, 0.024, 0.56])
        cbar = fig.colorbar(scalar, cax=cax)
        cbar.set_label("Objective on prior grid (lower is better)")
    handles, labels = axs[0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=min(len(labels), 3),
        )
    fig.suptitle(title, fontsize=15, y=1.08)
    if scalar is None:
        fig.subplots_adjust(top=0.77, wspace=0.28)
    return _save_figure(fig, filename)


__all__ = ["plot_objective_summary"]
