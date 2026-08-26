"""Objective-landscape figures."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from pyage.workflows.plots.common import (
    GRID_CMAP,
    OBSERVED_COLOR,
    _best_row,
    _ensure_frame,
    _method_color,
    _nearest_reference_objective_row,
    _plot_interpolated_objective_surface,
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


def _plot_solution_objective_axis(
    ax,
    grid: pd.DataFrame,
    grid_values: pd.Series,
    posterior: pd.DataFrame,
    posterior_values: pd.Series,
    x_name: str,
    objective_column: str,
    posterior_objective_column: str,
    best_posterior: pd.Series | None,
    reference_params: dict[str, float] | None,
    reference_row: pd.Series | None,
    vmin: float,
    vmax: float,
):
    """Plot one parameter against objective values."""
    scalar = ax.scatter(
        grid[x_name],
        grid_values,
        c=grid_values,
        s=18,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
        alpha=0.24,
        edgecolors="none",
    )
    ax.scatter(
        posterior[x_name],
        posterior_values,
        c=posterior_values,
        s=34,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
        alpha=0.78,
        edgecolors="none",
        linewidths=0.2,
        zorder=4,
    )
    if best_posterior is not None:
        ax.scatter(
            best_posterior[x_name],
            best_posterior[posterior_objective_column],
            marker="*",
            s=140,
            color="white",
            edgecolor=OBSERVED_COLOR,
            linewidth=0.9,
            zorder=5,
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
            zorder=6,
        )
    ax.set_xlabel(x_name)
    ax.set_ylabel("Objective function")
    ax.set_title(f"{x_name} vs objective")
    return scalar


def _plot_solution_parameter_axis(
    ax,
    grid: pd.DataFrame,
    grid_values: pd.Series,
    posterior: pd.DataFrame,
    posterior_values: pd.Series,
    x_name: str,
    y_name: str,
    best_posterior: pd.Series | None,
    reference_params: dict[str, float] | None,
    vmin: float,
    vmax: float,
):
    """Plot two parameters over the interpolated objective landscape."""
    scalar = _plot_interpolated_objective_surface(
        ax,
        grid[x_name],
        grid[y_name],
        grid_values,
        vmin=vmin,
        vmax=vmax,
    )
    ax.scatter(
        grid[x_name],
        grid[y_name],
        s=10,
        color="#d9e2e8",
        alpha=0.08,
        edgecolors="none",
        zorder=2,
    )
    ax.scatter(
        posterior[x_name],
        posterior[y_name],
        c=posterior_values,
        s=34,
        cmap="viridis",
        vmin=vmin,
        vmax=vmax,
        alpha=0.82,
        edgecolors="none",
        linewidths=0.2,
        zorder=4,
    )
    if best_posterior is not None:
        ax.scatter(
            best_posterior[x_name],
            best_posterior[y_name],
            marker="*",
            s=140,
            color="white",
            edgecolor=OBSERVED_COLOR,
            linewidth=0.9,
            zorder=5,
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
            zorder=6,
        )
    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    ax.set_title(f"{x_name} vs {y_name}")
    return scalar


def _solution_legend(reference_params, reference_label: str) -> list[Line2D]:
    """Build the fixed legend for expert objective figures."""
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=7,
            markerfacecolor="#808080",
            markeredgecolor="none",
            alpha=0.55,
            label="Interpolated prior objective surface",
        ),
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markersize=7,
            markerfacecolor="#2b8cbe",
            markeredgecolor="none",
            label="Posterior solutions colored by objective",
        ),
        Line2D(
            [],
            [],
            marker="*",
            linestyle="",
            markersize=12,
            markerfacecolor="white",
            markeredgecolor=OBSERVED_COLOR,
            label="Best posterior solution",
        ),
    ]
    if reference_params:
        handles.append(
            Line2D(
                [],
                [],
                marker="D",
                linestyle="",
                markersize=8,
                markerfacecolor=OBSERVED_COLOR,
                markeredgecolor="white",
                label=reference_label,
            )
        )
    return handles


def plot_objective_solution_map(
    objective_frame: pd.DataFrame,
    posterior_frame: pd.DataFrame,
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "True parameters",
    filename: str | Path | None = None,
    title: str = "Expert view: posterior solutions colored by objective value",
):
    """
    Plot posterior solutions on top of the colored objective landscape.
    """
    apply_example_style()
    if not param_names:
        raise ValueError("At least one parameter is required.")

    objective_col = (
        "half_log_chi_square"
        if "half_log_chi_square" in objective_frame.columns
        else "obj_function"
    )
    posterior_objective_col = (
        "obj_function" if "obj_function" in posterior_frame.columns else objective_col
    )
    if objective_col not in objective_frame.columns:
        raise ValueError(
            "Objective frame must contain 'half_log_chi_square' or 'obj_function'."
        )
    if posterior_objective_col not in posterior_frame.columns:
        raise ValueError(
            "Posterior frame must contain 'obj_function' or 'half_log_chi_square'."
        )

    if len(param_names) == 1:
        pairs = [(param_names[0], objective_col)]
    else:
        pairs = list(combinations(param_names, 2))
    pairs = pairs[:3]

    ncols = len(pairs)
    fig_width = 5.8 * ncols + 1.6
    fig, axs = plt.subplots(1, ncols, figsize=(fig_width, 4.9), squeeze=False)
    axs = axs.flatten()

    grid_frame = objective_frame.copy()
    if len(grid_frame) > 9000:
        grid_frame = grid_frame.sample(9000, random_state=12345)
    post_frame = posterior_frame.copy()
    if len(post_frame) > 2500:
        post_frame = post_frame.sample(2500, random_state=12345)

    grid_values = pd.to_numeric(grid_frame[objective_col], errors="coerce")
    posterior_values = pd.to_numeric(
        post_frame[posterior_objective_col], errors="coerce"
    )
    combined_values = pd.concat(
        [grid_values.dropna(), posterior_values.dropna()], ignore_index=True
    )
    if combined_values.empty:
        raise ValueError(
            "No valid objective values found for the expert objective plot."
        )

    vmin = float(combined_values.min())
    vmax = float(combined_values.max())
    best_posterior = _best_row(post_frame)
    nearest_reference_row = _nearest_reference_objective_row(
        objective_frame,
        reference_params,
        param_names,
    )

    for xname, yname in pairs:
        ax = axs[pairs.index((xname, yname))]
        if yname == objective_col:
            scalar = _plot_solution_objective_axis(
                ax,
                grid_frame,
                grid_values,
                post_frame,
                posterior_values,
                xname,
                objective_col,
                posterior_objective_col,
                best_posterior,
                reference_params,
                nearest_reference_row,
                vmin,
                vmax,
            )
        else:
            scalar = _plot_solution_parameter_axis(
                ax,
                grid_frame,
                grid_values,
                post_frame,
                posterior_values,
                xname,
                yname,
                best_posterior,
                reference_params,
                vmin,
                vmax,
            )

    plot_right = 0.80 if ncols == 1 else 0.84
    colorbar_left = 0.88 if ncols == 1 else 0.90
    fig.subplots_adjust(left=0.10, right=plot_right, bottom=0.12, top=0.78, wspace=0.28)
    cax = fig.add_axes([colorbar_left, 0.18, 0.024, 0.58])
    cbar = fig.colorbar(scalar, cax=cax)
    cbar.set_label("Objective value (lower is better)")

    legend_handles = _solution_legend(reference_params, reference_label)
    fig.legend(
        legend_handles,
        [handle.get_label() for handle in legend_handles],
        loc="upper center",
        bbox_to_anchor=(0.48, 1.0),
        ncol=min(len(legend_handles), 3),
    )
    fig.suptitle(title, fontsize=15, y=1.08)
    return _save_figure(fig, filename)


__all__ = ["plot_objective_solution_map", "plot_objective_summary"]
