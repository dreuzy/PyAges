"""Single-date observation and reachable-model figures."""

from __future__ import annotations

from itertools import combinations
from math import ceil
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from pyage.workflows.plots.common import (
    MEDIAN_COLOR,
    OBSERVED_COLOR,
    REACHABLE_COLOR,
    _axis_label,
    _best_row,
    _ensure_frame,
    _method_color,
    _pretty_tracer_name,
    _reachable_column_name,
    _reference_concentration_lookup,
    _save_figure,
    apply_example_style,
)


def _plot_posterior_samples(
    ax,
    x_column: str,
    y_column: str,
    results: dict[str, object],
    *,
    show_labels: bool,
) -> None:
    """Add posterior clouds and best solutions to one concentration panel."""
    for method_index, (method_name, result) in enumerate(results.items()):
        frame = _ensure_frame(result)
        if x_column not in frame.columns or y_column not in frame.columns:
            continue
        color = _method_color(method_name, method_index)
        sample = frame[[x_column, y_column]].dropna()
        if len(sample) > 450:
            sample = sample.sample(450, random_state=12345)
        ax.scatter(
            sample[x_column],
            sample[y_column],
            s=20,
            alpha=0.18,
            color=color,
            linewidths=0,
            label=f"{method_name} posterior samples" if show_labels else None,
        )
        best = _best_row(frame)
        if best is not None:
            ax.scatter(
                best[x_column],
                best[y_column],
                marker="*",
                s=150,
                color=color,
                edgecolor="white",
                linewidth=0.8,
                label=f"{method_name} posterior best" if show_labels else None,
                zorder=4,
            )


def _plot_reference_point(
    ax,
    observed: pd.DataFrame,
    indices: tuple[int, int],
    reference_lookup,
    reference_label: str,
    *,
    show_label: bool,
) -> None:
    """Add an optional reference-model point to one panel."""
    if reference_lookup is None:
        return
    i0, i1 = indices
    x_key = (observed.loc[i0, "element"], observed.loc[i0, "date"])
    y_key = (observed.loc[i1, "element"], observed.loc[i1, "date"])
    if x_key not in reference_lookup.index or y_key not in reference_lookup.index:
        return
    ax.scatter(
        float(reference_lookup.loc[x_key]),
        float(reference_lookup.loc[y_key]),
        marker="D",
        s=80,
        color=MEDIAN_COLOR,
        edgecolor="white",
        linewidth=0.8,
        label=reference_label if show_label else None,
        zorder=6,
    )


def plot_single_date_model_space(
    concentration_sampled,
    reachable_frame: pd.DataFrame,
    posterior_results: dict[str, object],
    reference_concentrations=None,
    reference_label: str = "Reference model",
    filename: str | Path | None = None,
    title: str = "Observed concentrations, reachable space and calibrated models",
):
    """
    Plot pairwise concentration panels for the single-date example.
    """
    apply_example_style()
    observed = concentration_sampled.cv.reset_index(drop=True)
    reference_lookup = _reference_concentration_lookup(reference_concentrations)
    concentration_columns = concentration_sampled.names_dates()
    reachable_columns = [
        _reachable_column_name(row["element"], float(row["date"]))
        for _, row in observed.iterrows()
    ]
    pairs = list(combinations(range(len(concentration_columns)), 2))
    if not pairs:
        raise ValueError("At least two tracers are required to plot model space.")
    if len(concentration_columns) >= 4:
        pairs = pairs[:4]

    ncols = 2 if len(pairs) >= 4 else len(pairs)
    nrows = ceil(len(pairs) / ncols)
    fig, axs = plt.subplots(
        nrows,
        ncols,
        figsize=(5.4 * ncols, 4.6 * nrows),
        squeeze=False,
    )
    axs = axs.flatten()

    for ax_index, ((i0, i1), ax) in enumerate(zip(pairs, axs)):
        xcol = concentration_columns[i0]
        ycol = concentration_columns[i1]
        xcol_reach = reachable_columns[i0]
        ycol_reach = reachable_columns[i1]
        ax.scatter(
            reachable_frame[xcol_reach],
            reachable_frame[ycol_reach],
            s=16,
            alpha=0.35,
            color=REACHABLE_COLOR,
            edgecolors="none",
            label="Prior reachable space" if ax_index == 0 else None,
        )

        _plot_posterior_samples(
            ax,
            xcol,
            ycol,
            posterior_results,
            show_labels=ax_index == 0,
        )

        ax.scatter(
            observed.loc[i0, "concentration"],
            observed.loc[i1, "concentration"],
            marker="o",
            s=90,
            color=OBSERVED_COLOR,
            edgecolor="white",
            linewidth=0.8,
            label="Observation" if ax_index == 0 else None,
            zorder=5,
        )
        _plot_reference_point(
            ax,
            observed,
            (i0, i1),
            reference_lookup,
            reference_label,
            show_label=ax_index == 0,
        )
        ax.set_title(
            f"{_pretty_tracer_name(observed.loc[i0, 'element'])} vs {_pretty_tracer_name(observed.loc[i1, 'element'])}"
        )
        ax.set_xlabel(
            _axis_label(observed.loc[i0, "element"], observed.loc[i0].get("unit"))
        )
        ax.set_ylabel(
            _axis_label(observed.loc[i1, "element"], observed.loc[i1].get("unit"))
        )

    for ax in axs[len(pairs) :]:
        ax.remove()

    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=min(len(labels), 3),
    )
    fig.suptitle(title, fontsize=15, y=1.08)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return _save_figure(fig, filename)


__all__ = ["plot_single_date_model_space"]
