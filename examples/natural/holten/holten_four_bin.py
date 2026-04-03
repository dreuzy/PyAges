# -*- coding: utf-8 -*-
"""
Holten-specific local 4-bin fitting utilities.

This module implements a benchmark-oriented discrete age-distribution fit
for the Holten example, using the article-like bins:
0-20 years, 20-40 years, 40-60 years, and an old fraction (>60 years).

The implementation is intentionally local to the example because the old
end-member is tracer-specific and should not yet be pushed into the generic
PyAge LPM stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

from holten_benchmark import build_reference_curve
from holten_case import PreparedHoltenCase, build_context, load_yaml


BIN_DEFINITIONS = (
    {"name": "f_0_20", "label": "0-20", "age_min": 0.0, "age_max": 20.0, "representative_age": 10.0},
    {"name": "f_20_40", "label": "20-40", "age_min": 20.0, "age_max": 40.0, "representative_age": 30.0},
    {"name": "f_40_60", "label": "40-60", "age_min": 40.0, "age_max": 60.0, "representative_age": 50.0},
    {"name": "f_old", "label": ">60", "age_min": 60.0, "age_max": np.inf, "representative_age": 310.0},
)
BIN_ORDER = [item["name"] for item in BIN_DEFINITIONS]


def _reference_year(prepared: PreparedHoltenCase) -> float:
    return float(prepared.observed_aggregated["date"].median())


def _old_endmember_value(prepared: PreparedHoltenCase, tracer_name: str, reference_year: float) -> float:
    tracer_cfg = load_yaml(prepared.context.paths.tracer_source_dir / tracer_name / f"{tracer_name}.yaml")
    holten_cfg = tracer_cfg["holten"]
    if tracer_name == "39Ar":
        return float(holten_cfg["old_endmember"]["value"])
    if tracer_name == "kr85":
        return float(holten_cfg["old_endmember"]["value"])
    if tracer_name == "3H":
        premodern = float(holten_cfg["premodern_input"]["value"])
        decay_time = float(tracer_cfg["decay_time"])
        # The old bin starts at >60 years. Using 60 years gives a conservative
        # upper estimate for present-day tritium in the old fraction, and the
        # resulting value is already extremely close to zero.
        age_years = max(60.0, reference_year - 1953.0)
        return float(premodern * np.exp(-age_years / decay_time))
    raise ValueError(f"Unsupported tracer for Holten 4-bin fit: {tracer_name}")


def _reference_curve_value(
    tracer_name: str,
    tracer_cfg: dict[str, Any],
    display_history: pd.DataFrame,
    reference_year: float,
    recharge_year: np.ndarray,
) -> np.ndarray:
    recharge_year = np.asarray(recharge_year, dtype=float)
    dates = display_history["date"].astype(float).to_numpy()
    values = display_history["concentration"].astype(float).to_numpy()
    interp = np.interp(recharge_year, dates, values, left=np.nan, right=values[-1])

    missing = np.isnan(interp)
    if missing.any():
        decay_time = float(tracer_cfg["decay_time"])
        if tracer_name == "3H":
            premodern = float(tracer_cfg["holten"]["premodern_input"]["value"])
            ages = reference_year - recharge_year[missing]
            interp[missing] = premodern * np.exp(-ages / decay_time)
        elif tracer_name == "kr85":
            interp[missing] = float(tracer_cfg["holten"]["old_endmember"]["value"])
        elif tracer_name == "39Ar":
            interp[missing] = values[0]
        else:
            raise ValueError(f"Unsupported tracer for interpolation fallback: {tracer_name}")
    return interp


def build_4bin_endmembers(prepared: PreparedHoltenCase) -> pd.DataFrame:
    reference_year = _reference_year(prepared)
    rows: list[dict[str, Any]] = []

    for tracer_name, raw_history in prepared.tracer_histories.items():
        observed = prepared.observed_aggregated.loc[prepared.observed_aggregated["element"] == tracer_name].copy()
        display_history = build_reference_curve(prepared, tracer_name, raw_history, observed)
        tracer_cfg = load_yaml(prepared.context.paths.tracer_source_dir / tracer_name / f"{tracer_name}.yaml")
        dates = display_history["date"].astype(float)
        unit = str(display_history["unit"].iloc[0])

        for spec in BIN_DEFINITIONS[:-1]:
            age_min = float(spec["age_min"])
            age_max = float(spec["age_max"])
            lower_date = reference_year - age_max
            upper_date = reference_year - age_min
            sample_dates = np.linspace(lower_date, upper_date, 120)
            sample_values = _reference_curve_value(tracer_name, tracer_cfg, display_history, reference_year, sample_dates)
            rows.append(
                {
                    "tracer": tracer_name,
                    "bin_name": spec["name"],
                    "bin_label": spec["label"],
                    "age_min": age_min,
                    "age_max": age_max,
                    "representative_age": spec["representative_age"],
                    "concentration": float(sample_values.mean()),
                    "unit": unit,
                }
            )

        old_spec = BIN_DEFINITIONS[-1]
        rows.append(
            {
                "tracer": tracer_name,
                "bin_name": old_spec["name"],
                "bin_label": old_spec["label"],
                "age_min": old_spec["age_min"],
                "age_max": np.nan,
                "representative_age": old_spec["representative_age"],
                "concentration": _old_endmember_value(prepared, tracer_name, reference_year),
                "unit": unit,
            }
        )

    return pd.DataFrame(rows)


def _stick_breaking_fractions(z: np.ndarray) -> dict[str, float]:
    v1, v2, v3 = expit(z)
    f1 = float(v1)
    f2 = float((1.0 - f1) * v2)
    f3 = float((1.0 - f1 - f2) * v3)
    f4 = float(1.0 - f1 - f2 - f3)
    return {
        "f_0_20": f1,
        "f_20_40": f2,
        "f_40_60": f3,
        "f_old": f4,
    }


def _endmember_matrix(endmembers: pd.DataFrame, tracer_order: list[str]) -> np.ndarray:
    matrix = np.zeros((len(tracer_order), len(BIN_ORDER)), dtype=float)
    for i, tracer_name in enumerate(tracer_order):
        subset = endmembers.loc[endmembers["tracer"] == tracer_name].copy()
        subset = subset.set_index("bin_name").loc[BIN_ORDER]
        matrix[i, :] = subset["concentration"].to_numpy(dtype=float)
    return matrix


def fit_well_4bin(prepared: PreparedHoltenCase, well_id: str, endmembers: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    obs = prepared.observed_by_well[well_id].copy()
    tracer_order = obs["element"].tolist()
    y = obs["concentration"].to_numpy(dtype=float)
    sigma = obs["error"].to_numpy(dtype=float)
    matrix = _endmember_matrix(endmembers, tracer_order)

    def objective(z: np.ndarray) -> float:
        fractions = _stick_breaking_fractions(z)
        f = np.asarray([fractions[name] for name in BIN_ORDER], dtype=float)
        residual = (matrix @ f - y) / sigma
        return float(np.sum(residual * residual))

    best = None
    for start in (
        np.zeros(3, dtype=float),
        np.array([1.0, 0.0, 0.0], dtype=float),
        np.array([-1.0, 0.5, 0.0], dtype=float),
    ):
        result = minimize(objective, x0=start, method="BFGS")
        if best is None or result.fun < best.fun:
            best = result

    assert best is not None
    fractions = _stick_breaking_fractions(best.x)
    f = np.asarray([fractions[name] for name in BIN_ORDER], dtype=float)
    modeled = matrix @ f
    residual = y - modeled
    weighted_residual = residual / sigma

    fit_rows: list[dict[str, Any]] = []
    for idx, tracer_name in enumerate(tracer_order):
        fit_rows.append(
            {
                "well_id": well_id,
                "tracer": tracer_name,
                "unit": str(obs.iloc[idx]["unit"]),
                "observed": float(y[idx]),
                "error": float(sigma[idx]),
                "modeled": float(modeled[idx]),
                "residual": float(residual[idx]),
                "weighted_residual": float(weighted_residual[idx]),
                **fractions,
            }
        )

    summary = {
        "well_id": well_id,
        **fractions,
        "chi2_local_4bin": float(np.sum(weighted_residual * weighted_residual)),
        "rmse_local_4bin": float(np.sqrt(np.mean(residual * residual))),
        "weighted_rmse_local_4bin": float(np.sqrt(np.mean(weighted_residual * weighted_residual))),
        "mean_age_local_4bin": float(
            sum(fractions[name] * spec["representative_age"] for name, spec in zip(BIN_ORDER, BIN_DEFINITIONS))
        ),
        "optimization_success": bool(best.success),
        "optimization_message": str(best.message),
    }
    return summary, pd.DataFrame(fit_rows)


def fit_all_wells_4bin(prepared: PreparedHoltenCase) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    endmembers = build_4bin_endmembers(prepared)
    summary_rows: list[dict[str, Any]] = []
    fit_frames: list[pd.DataFrame] = []
    for well_id in prepared.context.selected_wells:
        summary, fit_frame = fit_well_4bin(prepared, well_id, endmembers)
        summary_rows.append(summary)
        fit_frames.append(fit_frame)
    summary_df = pd.DataFrame(summary_rows)
    fit_df = pd.concat(fit_frames, ignore_index=True)
    return endmembers, summary_df, fit_df


def _plot_fraction_bars(summary: pd.DataFrame, output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(summary))
    bottom = np.zeros(len(summary), dtype=float)
    colors = ["#4c78a8", "#72b7b2", "#f2cf5b", "#d95f5f"]
    labels = [spec["label"] for spec in BIN_DEFINITIONS]
    for color, frac_name, label in zip(colors, BIN_ORDER, labels):
        values = summary[frac_name].to_numpy(dtype=float)
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


def _plot_modeled_vs_observed(fit_df: pd.DataFrame, output_dir: Path) -> Path:
    tracers = ["3H", "kr85", "39Ar"]
    fig, axes = plt.subplots(1, len(tracers), figsize=(12, 4.2), sharey=False)
    if len(tracers) == 1:
        axes = [axes]
    for ax, tracer_name in zip(axes, tracers):
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
    axes[0].legend(loc="best")
    fig.suptitle("Holten local 4-bin fit: observed vs modeled concentrations")
    fig.tight_layout()
    out_path = output_dir / "holten_4bin_observed_vs_modeled.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def write_4bin_outputs(
    endmembers: pd.DataFrame,
    summary: pd.DataFrame,
    fit_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    endmembers_path = output_dir / "holten_4bin_endmembers.csv"
    summary_path = output_dir / "holten_4bin_summary.csv"
    fit_path = output_dir / "holten_4bin_modeled_vs_observed.csv"
    endmembers.to_csv(endmembers_path, index=False)
    summary.to_csv(summary_path, index=False)
    fit_df.to_csv(fit_path, index=False)
    fraction_plot = _plot_fraction_bars(summary, output_dir)
    fit_plot = _plot_modeled_vs_observed(fit_df, output_dir)
    return {
        "endmembers": endmembers_path,
        "summary": summary_path,
        "fit": fit_path,
        "fractions_plot": fraction_plot,
        "fit_plot": fit_plot,
    }


def run_local_4bin(prepared: PreparedHoltenCase, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    endmembers, summary, fit_df = fit_all_wells_4bin(prepared)
    paths = write_4bin_outputs(endmembers, summary, fit_df, output_dir)
    return endmembers, summary, fit_df, paths


if __name__ == "__main__":
    ctx = build_context()
    raise SystemExit(f"Holten local 4-bin utilities are available for {ctx.paths.example_dir}")
