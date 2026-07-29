"""Small plotting helpers used by reusable high-level workflows."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(fig: plt.Figure, filename: str | Path | None) -> plt.Figure:
    if filename is not None:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=220, bbox_inches="tight")
    return fig


def plot_observations_overview(
    concentrations,
    filename: str | Path | None = None,
    title: str = "Observed concentrations",
) -> plt.Figure:
    """Plot one compact time-series panel per observed tracer."""
    frame = concentrations.cv.copy()
    tracers = list(dict.fromkeys(frame["element"].tolist()))
    ncols = min(3, max(len(tracers), 1))
    nrows = ceil(max(len(tracers), 1) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(5.2 * ncols, 3.6 * nrows),
        squeeze=False,
    )
    for ax, tracer in zip(axes.flat, tracers):
        observed = frame[frame["element"].eq(tracer)].sort_values("date")
        errors = (
            observed["error"]
            if "error" in observed
            and pd.to_numeric(observed["error"], errors="coerce").fillna(0).gt(0).any()
            else None
        )
        ax.errorbar(
            observed["date"],
            observed["concentration"],
            yerr=errors,
            fmt="o",
            capsize=2,
        )
        unit = observed["unit"].iloc[0] if "unit" in observed and not observed.empty else None
        ax.set_title(str(tracer).upper())
        ax.set_xlabel("Year")
        ax.set_ylabel(f"Concentration [{unit}]" if unit else "Concentration")
        ax.grid(alpha=0.25)
    for ax in list(axes.flat)[len(tracers):]:
        ax.remove()
    fig.suptitle(title)
    fig.tight_layout()
    return _save(fig, filename)


def plot_parameter_summary(
    results_by_method: dict[str, object],
    param_names: list[str],
    filename: str | Path | None = None,
    title: str = "Parameter distributions",
) -> plt.Figure:
    """Plot posterior histograms without site- or article-specific styling."""
    ncols = min(3, max(len(param_names), 1))
    nrows = ceil(max(len(param_names), 1) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(5.0 * ncols, 3.8 * nrows),
        squeeze=False,
    )
    for ax, parameter in zip(axes.flat, param_names):
        for method, result in results_by_method.items():
            frame = result.dist().copy() if hasattr(result, "dist") else pd.DataFrame(result)
            if parameter not in frame:
                continue
            values = pd.to_numeric(frame[parameter], errors="coerce").dropna()
            if values.empty:
                continue
            bins = min(max(int(np.sqrt(len(values))), 12), 30)
            ax.hist(values, bins=bins, density=True, alpha=0.45, label=method)
        ax.set_title(parameter)
        ax.set_xlabel(parameter)
        ax.set_ylabel("Density")
    for ax in list(axes.flat)[len(param_names):]:
        ax.remove()
    handles, labels = axes[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, frameon=False)
    fig.suptitle(title)
    fig.tight_layout()
    return _save(fig, filename)
