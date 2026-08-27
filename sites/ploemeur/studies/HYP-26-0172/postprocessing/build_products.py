# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build article tables and figures from HYP-26-0172 workflow outputs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..scripts.study_common import validate_profile
from .export import export_figure
from .style import (
    CONDITIONED,
    FULL_SERIES,
    MODEL_COLORS,
    OBSERVATIONS,
    UNCONSTRAINED,
    WELL_COLORS,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
STUDY_RESULTS = REPO_ROOT / "results" / "HYP-26-0172"
SCENARIO_RE = re.compile(
    r"ploemeur_(?P<conditioning>apriori_double_)?(?P<error>\d+(?:\.\d+)?)"
    r"(?P<mode>span_full|span_with_prior|successive_with_prior|successive)$"
)


def profile_root(profile: str) -> Path:
    return STUDY_RESULTS if profile == "production" else STUDY_RESULTS / profile


def run_directories(root: Path) -> list[Path]:
    runs = root / "runs"
    if not runs.is_dir():
        raise FileNotFoundError(f"No run directory found: {runs}")
    return sorted(path for path in runs.iterdir() if (path / "workflow").is_dir())


def latest_scenario_outputs(workflow: Path) -> list[tuple[Path, re.Match[str]]]:
    outputs: list[tuple[Path, re.Match[str]]] = []
    for scenario in workflow.iterdir() if workflow.is_dir() else []:
        if not scenario.is_dir() or not (match := SCENARIO_RE.fullmatch(scenario.name)):
            continue
        timestamps = [path for path in scenario.iterdir() if path.is_dir()]
        if timestamps:
            outputs.append(
                (max(timestamps, key=lambda path: path.stat().st_mtime), match)
            )
    return outputs


def collect_statistics(root: Path) -> pd.DataFrame:
    records: list[dict] = []
    for run_dir in run_directories(root):
        for output, match in latest_scenario_outputs(run_dir / "workflow"):
            # Read each calibration case directly. Unlike the historical
            # concatenated summaries, the directory name preserves the well.
            for stats_file in sorted(
                output.glob("*_????_????/*/Metropolis_Hastings/distributions_stats.txt")
            ):
                model_dir = stats_file.parents[1]
                case_dir = model_dir.parent
                case_match = re.fullmatch(
                    r"(?P<well>.+)_(?P<start>\d{4})_(?P<end>\d{4})", case_dir.name
                )
                if not case_match:
                    continue
                samples = pd.read_csv(stats_file, sep="\t")
                if samples.empty or "p50" not in samples:
                    continue
                record = {
                    "date": float(case_match.group("end")),
                    "window_start": int(case_match.group("start")),
                    "window_end": int(case_match.group("end")),
                    "well": case_match.group("well"),
                }
                for column in (
                    "p10",
                    "p25",
                    "p50",
                    "p75",
                    "p90",
                    "mean",
                ):
                    if column in samples:
                        record[f"{column}_mean"] = float(samples[column].mean())
                        record[f"{column}_std"] = float(samples[column].std(ddof=0))
                record.update(
                    experiment_id=run_dir.name,
                    scenario=output.parent.name,
                    output_directory=str(output.relative_to(REPO_ROOT)),
                    mode=match.group("mode"),
                    conditioned=bool(match.group("conditioning")),
                    relative_error=float(match.group("error")),
                    lpm=model_dir.name,
                )
                records.append(record)
    if not records:
        raise FileNotFoundError(
            f"No *_stats_quantiles.txt files found below {root / 'runs'}"
        )
    return pd.DataFrame.from_records(records)


def infer_well(experiment_id: str) -> str:
    for well in ("F09", "F11", "F38", "MF1", "PE"):
        if well in experiment_id:
            return well
    return "multiple"


def save_derived_tables(stats: pd.DataFrame, derived: Path) -> dict[str, Path]:
    derived.mkdir(parents=True, exist_ok=True)
    stats = stats.copy()
    if "well" not in stats:
        stats["well"] = stats["experiment_id"].map(infer_well)
    all_path = derived / "posterior_statistics.csv"
    stats.to_csv(all_path, index=False)

    tables = {"all": all_path}
    definitions = {
        "figure4_median_transit_times.csv": stats[
            stats["experiment_id"].str.startswith("main_")
            & stats["mode"].isin(["successive", "successive_with_prior"])
            & stats["lpm"].eq("exp_shifted")
        ],
        "figure5_model_comparison.csv": stats[
            stats["experiment_id"].str.startswith("main_")
            & stats["mode"].eq("successive_with_prior")
        ],
        "figure6_median_transit_times.csv": stats[
            (
                stats["experiment_id"].str.startswith("regime_")
                | stats["experiment_id"].str.startswith("main_")
            )
            & stats["mode"].eq("successive_with_prior")
            & stats["lpm"].eq("exp_shifted")
            & stats["relative_error"].eq(0.2)
        ],
        "figureA1_error_sensitivity.csv": stats[
            (
                stats["experiment_id"].str.startswith("error_")
                | stats["experiment_id"].str.startswith("main_")
            )
            & stats["mode"].eq("successive_with_prior")
        ],
        "F11_initialization_robustness.csv": stats[
            stats["experiment_id"].str.startswith("init_F11_")
        ],
        "F11_tracer_sensitivity.csv": stats[
            stats["experiment_id"].str.startswith("tracer_F11_")
            | stats["experiment_id"].str.startswith("main_F11_")
        ],
    }
    for filename, frame in definitions.items():
        path = derived / filename
        frame.to_csv(path, index=False)
        tables[filename] = path
    return tables


def collect_diagnostics(root: Path, derived: Path) -> Path:
    records = []
    for run_dir in run_directories(root):
        for result_file in (run_dir / "workflow").glob(
            "**/Metropolis_Hastings/results_calibration.txt"
        ):
            frame = pd.read_csv(result_file, sep="\t")
            values = (
                dict(zip(frame.iloc[:, 0], frame.iloc[:, 1], strict=False))
                if len(frame.columns) >= 2
                else {}
            )
            stats_file = result_file.with_name("distributions_stats.txt")
            finite = True
            if stats_file.is_file():
                samples = pd.read_csv(stats_file, sep="\t")
                finite = bool(
                    np.isfinite(
                        samples.select_dtypes(include="number").to_numpy()
                    ).all()
                )
            records.append(
                {
                    "experiment_id": run_dir.name,
                    "case": str(
                        result_file.parent.parent.relative_to(run_dir / "workflow")
                    ),
                    "success_rate": pd.to_numeric(
                        values.get("success_rate"), errors="coerce"
                    ),
                    "finite_posterior": finite,
                }
            )
    path = derived / "mcmc_diagnostics.csv"
    pd.DataFrame.from_records(
        records, columns=["experiment_id", "case", "success_rate", "finite_posterior"]
    ).to_csv(path, index=False)
    return path


def plot_figure4(frame: pd.DataFrame, figures: Path) -> list[Path]:
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


def _well_from_output(output_directory: str) -> str | None:
    path = REPO_ROOT / output_directory
    candidates = list(path.glob("*_????_????"))
    return candidates[0].name.split("_", 1)[0] if candidates else None


def plot_figure6(
    frame: pd.DataFrame, figures: Path, allow_partial: bool = False
) -> list[Path]:
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
        top.set_ylim(
            max(25, high["p50_mean"].min() - 8), high["p50_mean"].max() + 8
        )
        bottom.set_ylim(0, max(12, low["p50_mean"].max() + 3))
        top.spines.bottom.set_visible(False)
        bottom.spines.top.set_visible(False)
        top.tick_params(labeltop=False, bottom=False)
        bottom.xaxis.tick_bottom()
        kwargs = dict(
            marker=[(-1, -0.5), (1, 0.5)],
            markersize=8,
            linestyle="none",
            color="k",
            mec="k",
            mew=1,
            clip_on=False,
        )
        top.plot([0, 1], [0, 0], transform=top.transAxes, **kwargs)
        bottom.plot([0, 1], [1, 1], transform=bottom.transAxes, **kwargs)
    top.set_title("Shifted Exponential | error=20%", fontweight="bold")
    top.legend(frameon=False, ncol=2)
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[-1].set_xlabel("Date")
    fig.supylabel("Median transit time (years)")
    return export_figure(fig, figures, "Figure6")


def plot_figure_a1(frame: pd.DataFrame, figures: Path) -> list[Path]:
    if frame.empty:
        return []
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True, constrained_layout=True)
    for ax, well in zip(axes, ("F11", "F09"), strict=False):
        subset = frame[frame["well"].eq(well)]
        grouped = subset.groupby(["relative_error", "lpm"], as_index=False)[
            "p50_mean"
        ].mean()
        for model, data in grouped.groupby("lpm"):
            ax.plot(
                100 * data["relative_error"], data["p50_mean"], "o-", label=model
            )
        ax.set_title(well, loc="left", fontweight="bold")
        ax.grid(alpha=0.25)
    axes[0].legend(frameon=False)
    axes[-1].set_xlabel("Relative error (%)")
    fig.supylabel("Mean posterior median transit time (years)")
    return export_figure(fig, figures, "FigureA1")


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
