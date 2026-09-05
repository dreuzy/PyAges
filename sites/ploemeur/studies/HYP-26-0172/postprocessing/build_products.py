# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build HYP-26-0172 article figures from durable derived tables.

The extraction layer converts native workflow folders to stable CSV tables;
this façade selects those tables and delegates publication rendering. Keeping
the two stages explicit lets figures be rebuilt without rediscovering dated
execution directories.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..scripts.study_common import validate_profile
from .export import export_figure
from .product_extraction import (
    REPO_ROOT,
    collect_diagnostics,
    collect_statistics,
    latest_scenario_outputs,
    profile_root,
    run_directories,
    save_derived_tables,
)
from .style import (
    CONDITIONED,
    FULL_SERIES,
    OBSERVATIONS,
    UNCONSTRAINED,
)
from .summary_figures import (
    plot_figure4,
    plot_figure5,
    plot_figure6,
    plot_figure_a1,
)


def _prediction_file(
    output: Path, well: str, window: tuple[int, int], model: str = "exp_shifted"
) -> Path | None:
    path = (
        output
        / f"{well}_{window[0]}_{window[1]}"
        / model
        / "Metropolis_Hastings"
        / "concentrations_all_models.txt"
    )
    return path if path.is_file() else None


def _find_main_output(root: Path, well: str, mode: str) -> Path | None:
    prefix = f"main_{well}_"
    for run_dir in run_directories(root):
        if not run_dir.name.startswith(prefix):
            continue
        for output, match in latest_scenario_outputs(run_dir / "workflow"):
            if match.group("mode") == mode:
                return output
    return None


def plot_figure3(
    root: Path, figures: Path, window: tuple[int, int] = (2018, 2019)
) -> list[Path]:
    """Render posterior prediction ensembles for the two principal wells.

    Figure 3 is the declared exception to the derived-table-only rule because
    it needs joint posterior prediction curves. Native outputs are located by
    the extraction helpers, then reduced to the payload plotted here.
    """
    tracers = ("cfc11", "cfc12", "cfc113")
    payload = _figure3_payload(root, window)
    if payload is None:
        return []

    fig, axes = plt.subplots(
        2, 3, figsize=(13, 7), sharex=True, constrained_layout=True
    )
    for row, well in enumerate(("F09", "F11")):
        predictions, observations = payload[well]
        for col, tracer in enumerate(tracers):
            ax = axes[row, col]
            _plot_figure3_panel(ax, predictions, observations, tracer)
            if row == 0:
                ax.set_title(tracer.upper().replace("CFC", "CFC-"))
            if col == 0:
                ax.set_ylabel(f"{well}\nMixing ratio (pptv)")
            ax.set_xlim(2004, 2025)
            ax.grid(alpha=0.2)
    for ax in axes[-1]:
        ax.set_xlabel("Date")
    return export_figure(fig, figures, "Figure3")


def _figure3_payload(root: Path, window: tuple[int, int]) -> dict | None:
    payload = {}
    for well in ("F09", "F11"):
        outputs = {
            "independent": _find_main_output(root, well, "successive"),
            "conditioned": _find_main_output(root, well, "successive_with_prior"),
            "full": _find_main_output(root, well, "span_full"),
        }
        if not all(outputs.values()):
            return None
        full_cases = sorted(
            outputs["full"].glob(f"{well}_????_????"),
            key=lambda path: (
                int(path.name.rsplit("_", 1)[1]) - int(path.name.rsplit("_", 2)[1])
            ),
            reverse=True,
        )
        if not full_cases:
            return None
        files = {
            "independent": _prediction_file(outputs["independent"], well, window),
            "conditioned": _prediction_file(outputs["conditioned"], well, window),
            "full": full_cases[0]
            / "exp_shifted"
            / "Metropolis_Hastings"
            / "concentrations_all_models.txt",
        }
        if not all(path and path.is_file() for path in files.values()):
            return None
        observations = (
            outputs["independent"]
            / f"{well}_{window[0]}_{window[1]}"
            / "exp_shifted"
            / "concentrations.txt"
        )
        payload[well] = (
            {name: pd.read_csv(path, sep="\t") for name, path in files.items()},
            pd.read_csv(observations, sep="\t"),
        )
    return payload


def _plot_figure3_panel(ax, predictions: dict, observations: pd.DataFrame, tracer: str):
    for name, color, alpha in (
        ("full", FULL_SERIES, 0.15),
        ("independent", UNCONSTRAINED, 0.25),
        ("conditioned", CONDITIONED, 0.25),
    ):
        data = predictions[name]
        for column in (item for item in data if item.startswith(f"{tracer}_")):
            ax.plot(data["date"], data[column], color=color, alpha=alpha, linewidth=0.8)
    observed = observations[observations["element"].str.lower().eq(tracer)]
    ax.errorbar(
        observed["date"],
        observed["concentration"],
        yerr=observed["error"],
        fmt="o",
        color=OBSERVATIONS,
        markersize=3,
        capsize=2,
    )


def build(profile: str, allow_partial: bool = False) -> list[Path]:
    """Extract durable tables and render every figure available for a profile."""
    root = profile_root(profile)
    derived, figures = root / "derived", root / "figures"
    stats = collect_statistics(root)
    tables = save_derived_tables(stats, derived)
    outputs = list(tables.values())
    outputs.append(collect_diagnostics(root, derived))
    outputs += plot_figure3(root, figures)
    outputs += plot_figure4(
        pd.read_csv(tables["figure4_median_transit_times.csv"]), figures
    )
    outputs += plot_figure5(
        pd.read_csv(tables["figure5_model_comparison.csv"]), figures
    )
    outputs += plot_figure6(
        pd.read_csv(tables["figure6_median_transit_times.csv"]), figures, allow_partial
    )
    outputs += plot_figure_a1(
        pd.read_csv(tables["figureA1_error_sensitivity.csv"]), figures
    )
    return outputs


def main() -> None:
    """Build study products for the requested isolated campaign profile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        type=validate_profile,
        default="production",
        help="campaign profile to postprocess",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="render figures from an incomplete campaign",
    )
    args = parser.parse_args()
    for path in build(args.profile, args.allow_partial):
        print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
