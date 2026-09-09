# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Create the diagnostic figures for the local Holten four-bin benchmark.

The numerical fit and the Metropolis--Hastings sampling live in
``holten_four_bin``.  This module only turns their tabular outputs into PNG
figures.  Keeping that boundary explicit makes it possible to test or reuse
the scientific calculations without importing plotting code throughout the
benchmark implementation.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BIN_NAMES = ("f_0_20", "f_20_40", "f_40_60", "f_old")
BIN_LABELS = ("0-20", "20-40", "40-60", ">60")
TRACER_ORDER = ("3H", "kr85", "39Ar")


def plot_fraction_bars(summary: pd.DataFrame, output_dir: Path) -> Path:
    """Plot the fitted fraction in each age bin for every selected well."""
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(summary))
    bottom = np.zeros(len(summary), dtype=float)
    colors = ["#4c78a8", "#72b7b2", "#f2cf5b", "#d95f5f"]
    for color, fraction, label in zip(colors, BIN_NAMES, BIN_LABELS, strict=False):
        values = summary[fraction].to_numpy(dtype=float)
        ax.bar(x, values, bottom=bottom, color=color, label=label)
        bottom += values
    ax.set_xticks(x, summary["well_id"].tolist())
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Fraction")
    ax.set_title("Holten local 4-bin fit: estimated age fractions")
    ax.legend(title="Age bin")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out_path = output_dir / "holten_4bin_fractions.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_modeled_vs_observed(fit_df: pd.DataFrame, output_dir: Path) -> Path:
    """Compare modeled and measured tracer concentrations by well."""
    order_map = {name: idx for idx, name in enumerate(TRACER_ORDER)}
    tracers = sorted(
        fit_df["tracer"].astype(str).unique().tolist(),
        key=lambda name: order_map.get(name, 999),
    )
    ncols = 2 if len(tracers) > 3 else len(tracers)
    nrows = int(np.ceil(len(tracers) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(6.0 * ncols, 4.2 * nrows), sharey=False
    )
    axes_array = np.atleast_1d(axes).reshape(nrows, ncols)
    flat_axes = axes_array.ravel()
    for ax, tracer_name in zip(flat_axes, tracers, strict=False):
        subset = fit_df.loc[fit_df["tracer"] == tracer_name].copy()
        x = np.arange(len(subset))
        ax.errorbar(
            x,
            subset["observed"],
            yerr=subset["error"],
            fmt="o",
            color="#c13b31",
            label="Observed",
        )
        ax.scatter(x, subset["modeled"], marker="s", color="#1f4b99", label="Modeled")
        ax.set_xticks(x, subset["well_id"].tolist(), rotation=0)
        ax.set_title(tracer_name)
        ax.set_ylabel(f"Concentration [{subset.iloc[0]['unit']}]")
        ax.grid(axis="y", alpha=0.25)
    for ax in flat_axes[len(tracers) :]:
        ax.axis("off")
    flat_axes[0].legend(loc="best")
    fig.suptitle("Holten local 4-bin fit: observed vs modeled concentrations")
    fig.tight_layout()
    out_path = output_dir / "holten_4bin_observed_vs_modeled.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_fraction_posteriors(
    samples: pd.DataFrame,
    paper: pd.DataFrame,
    output_dir: Path,
) -> Path:
    """Plot marginal posterior fractions together with the paper values."""
    well_ids = list(samples["well_id"].drop_duplicates())
    fig, axes = plt.subplots(
        len(well_ids),
        len(BIN_NAMES),
        figsize=(3.4 * len(BIN_NAMES), 2.8 * len(well_ids)),
        sharex="col",
        sharey=False,
    )
    if len(well_ids) == 1:
        axes = np.asarray([axes])
    colors = dict(
        zip(BIN_NAMES, ("#4c78a8", "#72b7b2", "#f2cf5b", "#d95f5f"), strict=True)
    )
    titles = dict(zip(BIN_NAMES, BIN_LABELS, strict=True))
    for row_idx, well_id in enumerate(well_ids):
        group = samples.loc[samples["well_id"] == well_id]
        paper_row = paper.loc[paper["well_id"] == well_id].iloc[0]
        for col_idx, fraction in enumerate(BIN_NAMES):
            ax = axes[row_idx, col_idx]
            values = group[fraction].astype(float)
            q10 = float(values.quantile(0.10))
            q90 = float(values.quantile(0.90))
            median = float(values.quantile(0.50))
            paper_value = float(paper_row[fraction])
            ax.hist(values, bins=24, color=colors[fraction], alpha=0.75, density=True)
            ax.axvline(paper_value, color="black", linestyle="--", linewidth=1.6)
            ax.axvline(median, color="#1f4b99", linestyle="-", linewidth=1.2, alpha=0.9)
            if row_idx == 0:
                ax.set_title(titles[fraction])
            if col_idx == 0:
                ax.set_ylabel(f"{well_id}\ndensity")
            ax.set_xlim(0.0, 1.0)
            ax.grid(alpha=0.2)
            if q90 < 1e-4:
                ax.text(
                    0.98,
                    0.92,
                    f"posterior near 0\nq90={q90:.1e}",
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=8,
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "fc": "white",
                        "ec": "#b0b0b0",
                        "alpha": 0.9,
                    },
                )
            elif q10 > 0.75:
                ax.text(
                    0.98,
                    0.92,
                    f"high fraction\nq10={q10:.3f}",
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=8,
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "fc": "white",
                        "ec": "#b0b0b0",
                        "alpha": 0.9,
                    },
                )
            ax.text(
                0.98,
                0.74,
                f"paper={paper_value:.3g}\nmedian={median:.3g}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize=8,
                color="#333333",
            )
    fig.supxlabel("Fraction value")
    fig.suptitle(
        "Holten 4-bin fractions: local MH posterior with paper reference", y=1.02
    )
    fig.tight_layout()
    out_path = output_dir / "holten_4bin_mh_fraction_posteriors.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_fraction_interval_comparison(
    comparison: pd.DataFrame, output_dir: Path
) -> Path:
    """Compare paper fractions with the central posterior intervals."""
    panel_titles = {
        "f_0_20": "0-20 years",
        "f_20_40": "20-40 years",
        "f_40_60": "40-60 years",
        "f_old": "> 60 years",
    }
    axis_labels = {
        "f_0_20": r"$f_1$",
        "f_20_40": r"$f_2$",
        "f_40_60": r"$f_3$",
        "f_old": r"$f_4$",
    }
    fig, axes = plt.subplots(
        1, len(BIN_NAMES), figsize=(4.8 * len(BIN_NAMES), 5.2), sharey=True
    )
    if len(BIN_NAMES) == 1:
        axes = [axes]
    y = np.arange(len(comparison))
    for ax, fraction in zip(axes, BIN_NAMES, strict=False):
        lower = comparison[f"{fraction}_posterior_q10"].astype(float)
        median = comparison[f"{fraction}_posterior_median"].astype(float)
        upper = comparison[f"{fraction}_posterior_q90"].astype(float)
        paper = comparison[f"{fraction}_paper"].astype(float)
        ax.hlines(
            y,
            lower,
            upper,
            color="#4c78a8",
            linewidth=4,
            label="MH q10-q90" if fraction == BIN_NAMES[0] else None,
        )
        ax.scatter(
            median,
            y,
            color="#1f4b99",
            marker="o",
            s=90,
            label="MH median" if fraction == BIN_NAMES[0] else None,
            zorder=3,
        )
        ax.scatter(
            paper,
            y,
            color="#c13b31",
            marker="D",
            s=110,
            label="Paper value" if fraction == BIN_NAMES[0] else None,
            zorder=4,
        )
        ax.set_title(panel_titles[fraction], fontsize=17, fontweight="bold")
        ax.set_xlim(0.0, 1.0)
        ax.set_xlabel(axis_labels[fraction], fontsize=26)
        ax.tick_params(axis="both", labelsize=17)
        ax.grid(alpha=0.25)
    axes[0].set_yticks(y, comparison["well_id"].tolist())
    axes[0].legend(loc="best", fontsize=14, frameon=True)
    fig.tight_layout()
    out_path = output_dir / "holten_4bin_paper_vs_mh_intervals.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


__all__ = [
    "plot_fraction_bars",
    "plot_fraction_interval_comparison",
    "plot_fraction_posteriors",
    "plot_modeled_vs_observed",
]
