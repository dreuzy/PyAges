# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Calibrated parameter distribution figures."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

from pyages.workflows.plots.common import (
    OBSERVED_COLOR,
    _best_row,
    _ensure_frame,
    _method_color,
    _save_figure,
    apply_example_style,
)


def plot_parameter_summary(
    results_by_method: dict[str, object],
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "Reference parameters",
    filename: str | Path | None = None,
    title: str = "Parameter distributions",
):
    """
    Plot a compact set of parameter histograms.
    """
    apply_example_style()
    ncols = min(3, max(len(param_names), 1))
    nrows = ceil(max(len(param_names), 1) / ncols)
    fig, axs = plt.subplots(
        nrows, ncols, figsize=(5.0 * ncols, 3.8 * nrows), squeeze=False
    )

    for ax, param_name in zip(axs.flatten(), param_names, strict=False):
        for method_index, (method_name, result) in enumerate(results_by_method.items()):
            frame = _ensure_frame(result)
            if param_name not in frame.columns:
                continue
            color = _method_color(method_name, method_index)
            values = pd.to_numeric(frame[param_name], errors="coerce").dropna()
            if values.empty:
                continue
            bins = min(max(int(np.sqrt(len(values))), 12), 30)
            ax.hist(
                values,
                bins=bins,
                density=True,
                histtype="stepfilled" if method_index == 0 else "step",
                alpha=0.45 if method_index == 0 else 1.0,
                color=color,
                linewidth=1.8,
                label=f"{method_name} posterior",
            )
            best = _best_row(frame)
            if best is not None and param_name in best:
                ax.axvline(best[param_name], color=color, linestyle="--", linewidth=1.5)
        if reference_params and param_name in reference_params:
            ax.axvline(
                float(reference_params[param_name]),
                color=OBSERVED_COLOR,
                linestyle=":",
                linewidth=1.8,
                label=reference_label if ax is axs.flatten()[0] else None,
            )
        ax.set_title(param_name)
        ax.set_xlabel(param_name)
        ax.set_ylabel("Density")

    for ax in axs.flatten()[len(param_names) :]:
        ax.remove()

    handles, labels = axs[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=min(len(labels), 3),
        )
    fig.suptitle(title, fontsize=15, y=1.06)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return _save_figure(fig, filename)


def plot_parameter_distribution_comparison(
    distributions: dict[str, object],
    param_names: list[str],
    param_labels: dict[str, str] | None = None,
    param_density_labels: dict[str, str] | None = None,
    filename: str | Path | None = None,
    title: str | None = None,
):
    """
    Overlay posterior parameter distributions coming from different workflows.
    """
    apply_example_style()
    ncols = min(3, max(len(param_names), 1))
    nrows = ceil(max(len(param_names), 1) / ncols)
    fig, axs = plt.subplots(
        nrows, ncols, figsize=(5.2 * ncols, 3.9 * nrows), squeeze=False
    )

    color_cycle = plt.get_cmap("tab10")

    for ax, param_name in zip(axs.flatten(), param_names, strict=False):
        for dist_index, (label, result) in enumerate(distributions.items()):
            frame = _ensure_frame(result)
            if param_name not in frame.columns:
                continue
            values = pd.to_numeric(frame[param_name], errors="coerce").dropna()
            if values.empty:
                continue
            bins = min(max(int(np.sqrt(len(values))), 12), 32)
            color = color_cycle(dist_index % 10)
            ax.hist(
                values,
                bins=bins,
                density=True,
                histtype="step",
                linewidth=2.0,
                color=color,
                alpha=0.95,
                label=label,
            )
            ax.axvline(
                values.median(), color=color, linestyle="--", linewidth=1.6, alpha=0.85
            )
        display_name = (
            param_labels.get(param_name, param_name) if param_labels else param_name
        )
        density_name = (
            param_density_labels.get(param_name, display_name)
            if param_density_labels
            else display_name
        )
        ax.set_title("")
        ax.set_xlabel(display_name, fontsize=18)
        ax.set_ylabel(f"$p({density_name})$", fontsize=18)
        ax.tick_params(axis="both", labelsize=16)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))

    for ax in axs.flatten()[len(param_names) :]:
        ax.remove()

    handles, labels = axs[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=min(len(labels), 3),
            fontsize=13,
        )
    if title:
        fig.suptitle(title, fontsize=15, y=1.06)
        fig.tight_layout(rect=(0, 0, 1, 0.9))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save_figure(fig, filename)


__all__ = [
    "plot_parameter_distribution_comparison",
    "plot_parameter_summary",
]
