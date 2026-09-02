# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Reproduce the Holten four-bin benchmark with tritiogenic helium.

The script prepares coupled tritium/helium responses, selects the documented
forward convention, fits and samples three- and four-observable scenarios,
then writes comparison tables, figures, and a provenance manifest. It stays
local to the Holten example because the audited helium datum and old
end-members are properties of this study, not generic PyAges behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import chi2

from examples.natural.holten.holten_benchmark import build_reference_curve
from examples.natural.holten.holten_case import (
    PreparedHoltenCase,
    load_yaml,
    tracer_yaml_path,
)
from examples.natural.holten.holten_four_bin import (
    BIN_DEFINITIONS,
    BIN_ORDER,
    _reference_curve_value,
    build_4bin_endmembers,
    load_paper_4bin_fractions,
)
from examples.natural.holten.holten_prepare import prepare_holten_inputs
from pyages.tracer.simple_tracers import SyntheticTracer
from scripts.common.provenance import git_output
from scripts.common.provenance import sha256_file as _sha256

TRACERS_3 = ("3H", "kr85", "39Ar")
TRACERS_4 = ("3H", "3He_trit", "kr85", "39Ar")
TRACER_LABELS = {
    "3H": "³H",
    "3He_trit": "tritiogenic ³He",
    "kr85": "⁸⁵Kr",
    "39Ar": "³⁹Ar",
}
BIN_LABELS = ("0–20 yr", "20–40 yr", "40–60 yr", ">60 yr")
COLORS = ("#2c6eaa", "#58a58c", "#e0ad36", "#bd514a")


@dataclass(frozen=True)
class ForwardConvention:
    """Holten-specific convention for the coupled parent/daughter response."""

    name: str
    vadose_years: float
    decay_during_vadose: bool
    old_age_years: float = 310.0


@dataclass(frozen=True)
class SamplingConfig:
    """Control the local MH chains used for the Holten comparison."""

    nstep: int = 10_000
    burn_in: float = 0.2
    proposal_scale: float = 0.18
    nchains: int = 4
    seed: int = 12_345


FORWARD_CONVENTIONS = (
    ForwardConvention("no_vadose_shift", 0.0, False),
    ForwardConvention("two_year_shift", 2.0, False),
    ForwardConvention("two_year_shift_and_decay", 2.0, True),
)


def parent_daughter_response(
    initial: Any, age_years: Any, half_life: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return 3H and retained tritiogenic 3He for a closed saturated system."""

    initial_array = np.asarray(initial, dtype=float)
    age_array = np.asarray(age_years, dtype=float)
    decay_rate = np.log(2.0) / float(half_life)
    parent = initial_array * np.exp(-decay_rate * age_array)
    daughter = initial_array - parent
    return parent, daughter


def _reference_year(prepared: PreparedHoltenCase) -> float:
    return float(prepared.observed_aggregated["date"].median())


def _tritium_configuration(
    prepared: PreparedHoltenCase,
) -> tuple[dict[str, Any], float, float]:
    cfg = load_yaml(tracer_yaml_path(prepared.context, "3H"))
    half_life = float(cfg["half_life"])
    premodern = float(cfg["holten"]["premodern_input"]["value"])
    return cfg, half_life, premodern


def _interpolate_input(
    history: pd.DataFrame,
    recharge_year: Any,
    premodern: float,
) -> np.ndarray:
    years = np.asarray(recharge_year, dtype=float)
    dates = history["date"].to_numpy(dtype=float)
    values = history["concentration"].to_numpy(dtype=float)
    result = np.interp(years, dates, values, left=np.nan, right=values[-1])
    return np.where(np.isnan(result), premodern, result)


def build_coupled_tritium_tracers(
    prepared: PreparedHoltenCase,
    convention: ForwardConvention,
) -> tuple[SyntheticTracer, SyntheticTracer]:
    """Build coupled 3H and 3He synthetic tracers from one input history."""

    history = prepared.tracer_histories["3H"]
    _, half_life, premodern = _tritium_configuration(prepared)
    decay_rate = np.log(2.0) / half_life

    def initial_at_saturated_recharge(date: Any, age: Any) -> np.ndarray:
        recharge_year = np.asarray(date, dtype=float) - np.asarray(age, dtype=float)
        precipitation_year = recharge_year - convention.vadose_years
        initial = _interpolate_input(history, precipitation_year, premodern)
        if convention.decay_during_vadose:
            initial = initial * np.exp(-decay_rate * convention.vadose_years)
        return initial

    def tritium_fn(date: Any, age: Any) -> np.ndarray:
        parent, _ = parent_daughter_response(
            initial_at_saturated_recharge(date, age), age, half_life
        )
        return parent

    def helium_fn(date: Any, age: Any) -> np.ndarray:
        _, daughter = parent_daughter_response(
            initial_at_saturated_recharge(date, age), age, half_life
        )
        return daughter

    knots = history["date"].to_numpy(dtype=float) + convention.vadose_years
    common = {
        "unit": "TU",
        "datemin": float(history["date"].min()),
        "datemax": float(history["date"].max() + convention.vadose_years),
        "convolution_dates": knots,
    }
    return (
        SyntheticTracer(name="3H", concentration_fn=tritium_fn, **common),
        SyntheticTracer(name="3He_trit", concentration_fn=helium_fn, **common),
    )


def build_reproduction_endmembers(
    prepared: PreparedHoltenCase,
    convention: ForwardConvention,
) -> pd.DataFrame:
    """Build the four Visser end-members, keeping Kr and Ar unchanged."""

    baseline = build_4bin_endmembers(prepared)
    baseline = baseline.loc[baseline["tracer"].isin(("kr85", "39Ar"))].copy()
    tritium, helium = build_coupled_tritium_tracers(prepared, convention)
    reference_year = _reference_year(prepared)
    rows: list[dict[str, Any]] = []

    for tracer in (tritium, helium):
        for spec in BIN_DEFINITIONS[:-1]:
            ages = np.linspace(float(spec["age_min"]), float(spec["age_max"]), 120)
            values = np.asarray(
                tracer.get_concentration(reference_year, ages), dtype=float
            )
            rows.append(
                {
                    "tracer": tracer.name,
                    "bin_name": spec["name"],
                    "bin_label": spec["label"],
                    "age_min": float(spec["age_min"]),
                    "age_max": float(spec["age_max"]),
                    "representative_age": float(spec["representative_age"]),
                    "concentration": float(values.mean()),
                    "unit": tracer.unit,
                }
            )

        old = BIN_DEFINITIONS[-1]
        old_value = float(
            np.asarray(
                tracer.get_concentration(reference_year, convention.old_age_years)
            )
        )
        rows.append(
            {
                "tracer": tracer.name,
                "bin_name": old["name"],
                "bin_label": old["label"],
                "age_min": float(old["age_min"]),
                "age_max": np.nan,
                "representative_age": convention.old_age_years,
                "concentration": old_value,
                "unit": tracer.unit,
            }
        )

    coupled = pd.DataFrame(rows)
    order = {name: idx for idx, name in enumerate(TRACERS_4)}
    result = pd.concat([coupled, baseline], ignore_index=True)
    result["_order"] = result["tracer"].map(order)
    return (
        result.sort_values(["_order", "age_min"])
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def build_observations(
    prepared: PreparedHoltenCase, well_id: str, include_helium: bool
) -> pd.DataFrame:
    """Return ordered Holten concentrations, adding the audited He datum."""

    obs = prepared.observed_by_well[well_id].copy()
    if include_helium:
        helium = prepared.helium_diagnostics.loc[
            prepared.helium_diagnostics["well_id"] == well_id
        ].iloc[0]
        obs = pd.concat(
            [
                obs,
                pd.DataFrame(
                    [
                        {
                            "well_id": well_id,
                            "element": "3He_trit",
                            "concentration": float(helium["3He_trit_TU"]),
                            "error": float(helium["3He_err"]),
                            "unit": "TU",
                            "date": float(helium["date"]),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    tracer_order = TRACERS_4 if include_helium else TRACERS_3
    order = {name: idx for idx, name in enumerate(tracer_order)}
    obs["_order"] = obs["element"].map(order)
    return obs.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def _fractions(z: Any) -> np.ndarray:
    v1, v2, v3 = expit(np.asarray(z, dtype=float))
    f1 = v1
    f2 = (1.0 - f1) * v2
    f3 = (1.0 - f1 - f2) * v3
    return np.asarray([f1, f2, f3, 1.0 - f1 - f2 - f3], dtype=float)


def _matrix(endmembers: pd.DataFrame, tracers: list[str]) -> np.ndarray:
    rows = []
    for tracer in tracers:
        values = (
            endmembers.loc[endmembers["tracer"] == tracer]
            .set_index("bin_name")
            .loc[BIN_ORDER]
        )
        rows.append(values["concentration"].to_numpy(dtype=float))
    return np.asarray(rows, dtype=float)


def _objective(
    matrix: np.ndarray, values: np.ndarray, errors: np.ndarray, z: Any
) -> float:
    residual = (matrix @ _fractions(z) - values) / errors
    return float(residual @ residual)


def optimize_well(obs: pd.DataFrame, endmembers: pd.DataFrame) -> dict[str, Any]:
    """Find one well's maximum-likelihood four-bin fractions."""
    tracers = obs["element"].astype(str).tolist()
    values = obs["concentration"].to_numpy(dtype=float)
    errors = obs["error"].to_numpy(dtype=float)
    matrix = _matrix(endmembers, tracers)

    def objective(z: np.ndarray) -> float:
        return _objective(matrix, values, errors, z)

    starts = (
        np.zeros(3),
        np.array([1.0, 0.0, 0.0]),
        np.array([-1.0, 0.5, 0.0]),
        np.array([-2.0, -2.0, -2.0]),
    )
    candidates = [
        minimize(objective, start, method=method)
        for method in ("BFGS", "L-BFGS-B")
        for start in starts
    ]
    refined = min(candidates, key=lambda item: float(item.fun))
    candidates.append(minimize(objective, refined.x, method="Powell"))
    best = min(candidates, key=lambda item: float(item.fun))
    fractions = _fractions(best.x)
    modeled = matrix @ fractions
    return {
        "z": np.asarray(best.x, dtype=float),
        "fractions": fractions,
        "modeled": modeled,
        "matrix": matrix,
        "values": values,
        "errors": errors,
        "tracers": tracers,
        "chi2": float(best.fun),
        "success": bool(best.success),
        "message": str(best.message),
    }


def fit_scenario(
    prepared: PreparedHoltenCase,
    endmembers: pd.DataFrame,
    include_helium: bool,
    scenario: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit every selected well and return fractions and concentration residuals."""
    summaries: list[dict[str, Any]] = []
    concentration_rows: list[dict[str, Any]] = []
    for well_id in prepared.context.selected_wells:
        obs = build_observations(prepared, well_id, include_helium)
        result = optimize_well(obs, endmembers)
        fractions = result["fractions"]
        dof = len(obs) - 3
        summaries.append(
            {
                "scenario": scenario,
                "well_id": well_id,
                **{
                    name: float(value)
                    for name, value in zip(BIN_ORDER, fractions, strict=False)
                },
                "chi2": result["chi2"],
                "degrees_of_freedom": dof,
                "p_chi2": float(chi2.sf(result["chi2"], dof)) if dof > 0 else np.nan,
                "optimization_success": result["success"],
                "optimization_message": result["message"],
            }
        )
        for tracer, observed, error, modeled in zip(
            result["tracers"],
            result["values"],
            result["errors"],
            result["modeled"],
            strict=False,
        ):
            concentration_rows.append(
                {
                    "scenario": scenario,
                    "well_id": well_id,
                    "tracer": tracer,
                    "observed": float(observed),
                    "error": float(error),
                    "modeled": float(modeled),
                    "residual": float(observed - modeled),
                    "weighted_residual": float((observed - modeled) / error),
                }
            )
    return pd.DataFrame(summaries), pd.DataFrame(concentration_rows)


def sample_scenario(
    prepared: PreparedHoltenCase,
    endmembers: pd.DataFrame,
    include_helium: bool,
    scenario: str,
    config: SamplingConfig,
) -> pd.DataFrame:
    """Sample the likelihood with the same local stick-breaking MH scheme."""

    records: list[dict[str, Any]] = []
    burn_count = int(config.nstep * config.burn_in)
    for well_idx, well_id in enumerate(prepared.context.selected_wells):
        obs = build_observations(prepared, well_id, include_helium)
        optimum = optimize_well(obs, endmembers)
        for chain in range(config.nchains):
            rng = np.random.default_rng(
                config.seed
                + 10_000 * chain
                + 101 * well_idx
                + (1_000_000 if include_helium else 0)
            )
            current = optimum["z"].copy()
            current_obj = _objective(
                optimum["matrix"], optimum["values"], optimum["errors"], current
            )
            accepted = 0
            for step in range(config.nstep):
                proposal = current + rng.normal(scale=config.proposal_scale, size=3)
                proposal_obj = _objective(
                    optimum["matrix"], optimum["values"], optimum["errors"], proposal
                )
                if np.log(rng.random()) < min(0.0, -0.5 * (proposal_obj - current_obj)):
                    current = proposal
                    current_obj = proposal_obj
                    accepted += 1
                if step >= burn_count:
                    fractions = _fractions(current)
                    records.append(
                        {
                            "scenario": scenario,
                            "well_id": well_id,
                            "chain": chain,
                            "step": step,
                            "acceptance_rate": accepted / (step + 1),
                            "chi2": current_obj,
                            **{
                                name: float(value)
                                for name, value in zip(
                                    BIN_ORDER, fractions, strict=False
                                )
                            },
                        }
                    )
    return pd.DataFrame(records)


def _split_rhat(values: np.ndarray) -> float:
    """Classic between/within-chain R-hat; sufficient for run diagnostics."""

    nchains, n = values.shape
    chain_means = values.mean(axis=1)
    within = float(values.var(axis=1, ddof=1).mean())
    between = float(n * chain_means.var(ddof=1))
    variance = (n - 1.0) / n * within + between / n
    return float(np.sqrt(variance / within)) if within > 0.0 else 1.0


def summarize_samples(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize marginal fractions and chain convergence by scenario and well."""
    summaries: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for (scenario, well_id), group in samples.groupby(
        ["scenario", "well_id"], sort=False
    ):
        row: dict[str, Any] = {
            "scenario": scenario,
            "well_id": well_id,
            "nsamples": len(group),
        }
        diag: dict[str, Any] = {
            "scenario": scenario,
            "well_id": well_id,
            "acceptance_rate_min": float(
                group.groupby("chain")["acceptance_rate"].last().min()
            ),
            "acceptance_rate_max": float(
                group.groupby("chain")["acceptance_rate"].last().max()
            ),
        }
        for name in (*BIN_ORDER, "chi2"):
            series = group[name].astype(float)
            row[f"{name}_mean"] = float(series.mean())
            row[f"{name}_q10"] = float(series.quantile(0.10))
            row[f"{name}_median"] = float(series.quantile(0.50))
            row[f"{name}_q90"] = float(series.quantile(0.90))
            pivot = (
                group.pivot(index="chain", columns="step", values=name)
                .sort_index()
                .to_numpy(dtype=float)
            )
            diag[f"{name}_rhat"] = _split_rhat(pivot)
        summaries.append(row)
        diagnostics.append(diag)
    return pd.DataFrame(summaries), pd.DataFrame(diagnostics)


def compare_fractions(
    paper: pd.DataFrame,
    optimizer: pd.DataFrame,
    posterior: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare optimizer and posterior fractions with the Visser reference."""
    rows: list[dict[str, Any]] = []
    for scenario in optimizer["scenario"].unique():
        opt = optimizer.loc[optimizer["scenario"] == scenario].set_index("well_id")
        post = posterior.loc[posterior["scenario"] == scenario].set_index("well_id")
        for _, reference in paper.iterrows():
            well_id = str(reference["well_id"])
            for fraction in BIN_ORDER:
                rows.append(
                    {
                        "scenario": scenario,
                        "well_id": well_id,
                        "fraction": fraction,
                        "visser": float(reference[fraction]),
                        "optimizer": float(opt.loc[well_id, fraction]),
                        "posterior_q10": float(post.loc[well_id, f"{fraction}_q10"]),
                        "posterior_median": float(
                            post.loc[well_id, f"{fraction}_median"]
                        ),
                        "posterior_q90": float(post.loc[well_id, f"{fraction}_q90"]),
                    }
                )
    comparison = pd.DataFrame(rows)
    metric_rows: list[dict[str, Any]] = []
    for (scenario, estimate), values in comparison.assign(
        estimate="optimizer", difference=comparison["optimizer"] - comparison["visser"]
    ).groupby(["scenario", "estimate"]):
        diff = values["difference"].to_numpy(dtype=float)
        metric_rows.append(
            {
                "scenario": scenario,
                "estimate": estimate,
                "median_absolute_error": float(np.median(np.abs(diff))),
                "mean_absolute_error": float(np.mean(np.abs(diff))),
                "rmse": float(np.sqrt(np.mean(diff * diff))),
                "max_absolute_error": float(np.max(np.abs(diff))),
            }
        )
    for scenario, values in comparison.groupby("scenario"):
        diff = values["posterior_median"].to_numpy(dtype=float) - values[
            "visser"
        ].to_numpy(dtype=float)
        metric_rows.append(
            {
                "scenario": scenario,
                "estimate": "posterior_median",
                "median_absolute_error": float(np.median(np.abs(diff))),
                "mean_absolute_error": float(np.mean(np.abs(diff))),
                "rmse": float(np.sqrt(np.mean(diff * diff))),
                "max_absolute_error": float(np.max(np.abs(diff))),
            }
        )
    return comparison, pd.DataFrame(metric_rows)


def qualify_forward_conventions(
    prepared: PreparedHoltenCase,
    paper: pd.DataFrame,
) -> tuple[pd.DataFrame, ForwardConvention, pd.DataFrame]:
    """Select the documented forward convention nearest the published fit."""

    rows: list[dict[str, Any]] = []
    endmembers_by_name: dict[str, pd.DataFrame] = {}
    for convention in FORWARD_CONVENTIONS:
        endmembers = build_reproduction_endmembers(prepared, convention)
        endmembers_by_name[convention.name] = endmembers
        fitted, _ = fit_scenario(prepared, endmembers, True, convention.name)
        merged = fitted.merge(paper, on="well_id", suffixes=("", "_paper"))
        differences = np.concatenate(
            [
                merged[name].to_numpy(dtype=float)
                - merged[f"{name}_paper"].to_numpy(dtype=float)
                for name in BIN_ORDER
            ]
        )
        published_chi2 = (
            pd.read_csv(
                prepared.context.paths.reference_results_path,
                sep="\t",
            )
            .set_index("Well")
            .loc[prepared.context.selected_wells, "4bin_chi2"]
            .to_numpy(dtype=float)
        )
        chi2_diff = fitted["chi2"].to_numpy(dtype=float) - published_chi2
        rows.append(
            {
                **asdict(convention),
                "fraction_rmse_vs_visser": float(
                    np.sqrt(np.mean(differences * differences))
                ),
                "fraction_mae_vs_visser": float(np.mean(np.abs(differences))),
                "chi2_rmse_vs_visser": float(np.sqrt(np.mean(chi2_diff * chi2_diff))),
                "mean_fitted_chi2": float(fitted["chi2"].mean()),
            }
        )
    qualification = (
        pd.DataFrame(rows)
        .sort_values(["fraction_rmse_vs_visser", "chi2_rmse_vs_visser"])
        .reset_index(drop=True)
    )
    selected_name = str(qualification.iloc[0]["name"])
    selected = next(item for item in FORWARD_CONVENTIONS if item.name == selected_name)
    return qualification, selected, endmembers_by_name[selected_name]


def _response_functions(
    prepared: PreparedHoltenCase,
    convention: ForwardConvention,
) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    reference_year = _reference_year(prepared)
    tritium, helium = build_coupled_tritium_tracers(prepared, convention)
    functions: dict[str, Callable[[np.ndarray], np.ndarray]] = {
        "3H": lambda age: np.asarray(
            tritium.get_concentration(reference_year, age), dtype=float
        ),
        "3He_trit": lambda age: np.asarray(
            helium.get_concentration(reference_year, age), dtype=float
        ),
    }
    for tracer_name in ("kr85", "39Ar"):
        raw = prepared.tracer_histories[tracer_name]
        observed = prepared.observed_aggregated.loc[
            prepared.observed_aggregated["element"] == tracer_name
        ]
        display = build_reference_curve(prepared, tracer_name, raw, observed)
        cfg = load_yaml(tracer_yaml_path(prepared.context, tracer_name))
        functions[tracer_name] = lambda age, t=tracer_name, c=cfg, d=display: (
            _reference_curve_value(
                t, c, d, reference_year, reference_year - np.asarray(age, dtype=float)
            )
        )
    return functions


def plot_figure9_reproduction(
    prepared: PreparedHoltenCase,
    convention: ForwardConvention,
    endmembers: pd.DataFrame,
    output_path: Path,
) -> None:
    """Recreate the six tracer-tracer panels of Visser Figure 9."""

    responses = _response_functions(prepared, convention)
    ages = np.linspace(0.0, 310.0, 900)
    pairs = (
        ("3H", "3He_trit"),
        ("3H", "kr85"),
        ("3H", "39Ar"),
        ("3He_trit", "kr85"),
        ("3He_trit", "39Ar"),
        ("kr85", "39Ar"),
    )
    observations = {
        well_id: build_observations(prepared, well_id, True).set_index("element")
        for well_id in prepared.context.selected_wells
    }
    fig, axes = plt.subplots(2, 3, figsize=(14.5, 9.0))
    markers = ("o", "s", "^", "D", "P", "X", "v")
    for ax, (xtracer, ytracer) in zip(axes.ravel(), pairs, strict=False):
        ax.plot(
            responses[xtracer](ages),
            responses[ytracer](ages),
            color="#555555",
            lw=1.5,
            label="piston-flow response",
        )
        xend = (
            endmembers.loc[endmembers["tracer"] == xtracer]
            .set_index("bin_name")
            .loc[BIN_ORDER, "concentration"]
        )
        yend = (
            endmembers.loc[endmembers["tracer"] == ytracer]
            .set_index("bin_name")
            .loc[BIN_ORDER, "concentration"]
        )
        ax.plot(
            xend,
            yend,
            color="#8b6bb1",
            lw=1.0,
            ls="--",
            alpha=0.8,
            label="4-bin end-members",
        )
        for marker, (well_id, obs) in zip(markers, observations.items(), strict=False):
            ax.errorbar(
                obs.loc[xtracer, "concentration"],
                obs.loc[ytracer, "concentration"],
                xerr=obs.loc[xtracer, "error"],
                yerr=obs.loc[ytracer, "error"],
                fmt=marker,
                ms=6,
                capsize=2,
                label=well_id,
            )
        ax.set_xlabel(TRACER_LABELS[xtracer])
        ax.set_ylabel(TRACER_LABELS[ytracer])
        ax.grid(alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False)
    fig.suptitle(
        "Holten tracer–tracer diagrams — reproduction of Visser et al. Figure 9"
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_figure10b_reproduction(
    paper: pd.DataFrame,
    fitted: pd.DataFrame,
    output_path: Path,
) -> None:
    """Recreate the cumulative four-bin age distributions (Figure 10b)."""

    fig, axes = plt.subplots(2, 4, figsize=(14.0, 7.2), sharex=True, sharey=True)
    ages = np.asarray([0.0, 20.0, 40.0, 60.0, 310.0])
    for ax, well_id in zip(axes.ravel(), fitted["well_id"], strict=False):
        fit = fitted.loc[fitted["well_id"] == well_id].iloc[0]
        ref = paper.loc[paper["well_id"] == well_id].iloc[0]
        fit_cum = np.r_[0.0, np.cumsum([fit[name] for name in BIN_ORDER])]
        ref_cum = np.r_[0.0, np.cumsum([ref[name] for name in BIN_ORDER])]
        ax.step(
            ages,
            ref_cum,
            where="post",
            color="#c13b31",
            ls="--",
            lw=2,
            label="Visser 4-bin",
        )
        ax.step(
            ages,
            fit_cum,
            where="post",
            color="#1f4b99",
            lw=2,
            label="PyAges 4-observable",
        )
        ax.set_title(well_id)
        ax.grid(alpha=0.25)
    axes.ravel()[-1].axis("off")
    for ax in axes[-1, :-1]:
        ax.set_xlabel("Age (yr)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Cumulative fraction")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower right", bbox_to_anchor=(0.96, 0.08))
    fig.suptitle(
        "Holten cumulative four-bin distributions — reproduction of Visser Figure 10b"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_modeled_observed(concentrations: pd.DataFrame, output_path: Path) -> None:
    """Plot measured and modeled concentrations for the corrected scenario."""
    data = concentrations.loc[concentrations["scenario"] == "corrected_4_observables"]
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0))
    for ax, tracer in zip(axes.ravel(), TRACERS_4, strict=False):
        subset = data.loc[data["tracer"] == tracer]
        x = np.arange(len(subset))
        ax.errorbar(
            x,
            subset["observed"],
            yerr=subset["error"],
            fmt="o",
            capsize=3,
            color="#c13b31",
            label="observed",
        )
        ax.scatter(x, subset["modeled"], marker="s", color="#1f4b99", label="modeled")
        ax.set_xticks(x, subset["well_id"])
        ax.set_title(TRACER_LABELS[tracer])
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend()
    fig.suptitle("Holten four-observable fit: modeled and observed concentrations")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_new_figure3(comparison: pd.DataFrame, output_path: Path) -> None:
    """Plot Visser, current 3-observable, and corrected 4-observable fractions."""

    scenarios = {
        "current_3_observables": ("#888888", "o", "PyAges current: ³H, ⁸⁵Kr, ³⁹Ar"),
        "corrected_4_observables": (
            "#1f4b99",
            "s",
            "PyAges corrected: ³H, tritiogenic ³He, ⁸⁵Kr, ³⁹Ar",
        ),
    }
    wells = comparison["well_id"].drop_duplicates().tolist()
    fig, axes = plt.subplots(1, 4, figsize=(18.5, 5.5), sharey=True)
    y = np.arange(len(wells))
    for ax, fraction, title in zip(axes, BIN_ORDER, BIN_LABELS, strict=False):
        visser = (
            comparison.loc[
                (comparison["scenario"] == "corrected_4_observables")
                & (comparison["fraction"] == fraction)
            ]
            .set_index("well_id")
            .loc[wells]
        )
        ax.scatter(
            visser["visser"],
            y,
            marker="D",
            color="#c13b31",
            s=65,
            label="Visser et al. (2013)",
            zorder=5,
        )
        for offset, (scenario, (color, marker, label)) in zip(
            (-0.13, 0.13), scenarios.items(), strict=False
        ):
            data = (
                comparison.loc[
                    (comparison["scenario"] == scenario)
                    & (comparison["fraction"] == fraction)
                ]
                .set_index("well_id")
                .loc[wells]
            )
            yy = y + offset
            ax.hlines(
                yy,
                data["posterior_q10"],
                data["posterior_q90"],
                color=color,
                lw=3,
                alpha=0.8,
            )
            ax.scatter(
                data["posterior_median"],
                yy,
                marker=marker,
                color=color,
                s=55,
                label=label,
                zorder=4,
            )
        ax.set_title(title, fontweight="bold")
        ax.set_xlim(0.0, 1.0)
        ax.set_xlabel("Fraction")
        ax.grid(alpha=0.25)
    axes[0].set_yticks(y, wells)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(
        "Figure 3 — Holten four-bin fractions: effect of restoring tritiogenic ³He"
    )
    fig.tight_layout(rect=(0, 0.13, 1, 0.95))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_manifest(
    prepared: PreparedHoltenCase,
    output_dir: Path,
    selected: ForwardConvention,
    config: SamplingConfig,
    generated: list[Path],
) -> Path:
    """Record inputs, software, Git state, conventions, and generated outputs."""
    root = Path(__file__).resolve().parents[3]
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=root, check=True, capture_output=True
    ).stdout
    inputs = [
        prepared.context.paths.sampling_raw_path,
        prepared.context.paths.tritium_raw_path,
        prepared.context.paths.kr85_raw_path,
        prepared.context.paths.reference_results_path,
        prepared.context.paths.doc_dir / "visser_shape_free_models.csv",
    ]
    code_paths = [
        Path(__file__).resolve(),
        root / "tests" / "examples" / "test_holten_reproduction.py",
        root / "holten_helium_requalification.md",
    ]
    manifest = {
        "description": "Holten reproduction with corrected tritiogenic 3He parent-daughter response",
        "git": {
            "commit": git_output(root, "rev-parse", "HEAD").strip(),
            "status_porcelain": git_output(root, "status", "--short").strip(),
            "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "forward_model": {
            "formula_parent": "3H = H0 * exp(-ln(2) * age / 12.32)",
            "formula_daughter": "3He_trit = H0 * (1 - exp(-ln(2) * age / 12.32))",
            "selected_convention": asdict(selected),
            "helium_sigma_59_05_TU": 0.5,
            "helium_sigma_59_05_basis": "median of the six reported selected-well uncertainties; source table is blank",
        },
        "sampling": asdict(config),
        "inputs": {str(path.relative_to(root)): _sha256(path) for path in inputs},
        "code_and_report": {
            str(path.relative_to(root)): _sha256(path) for path in code_paths
        },
        "outputs": {
            str(path.relative_to(root)): _sha256(path)
            for path in generated
            if path.exists()
        },
    }
    path = output_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def run_reproduction(output_dir: Path, sampling: SamplingConfig) -> dict[str, Path]:
    """Execute the complete Holten reproduction and return its artifact paths."""
    prepared = prepare_holten_inputs()
    output_dir.mkdir(parents=True, exist_ok=True)
    paper = load_paper_4bin_fractions(prepared)
    qualification, convention, endmembers4 = qualify_forward_conventions(
        prepared, paper
    )
    endmembers3 = build_4bin_endmembers(prepared)

    fit3, concentrations3 = fit_scenario(
        prepared, endmembers3, False, "current_3_observables"
    )
    fit4, concentrations4 = fit_scenario(
        prepared, endmembers4, True, "corrected_4_observables"
    )
    samples3 = sample_scenario(
        prepared, endmembers3, False, "current_3_observables", sampling
    )
    samples4 = sample_scenario(
        prepared, endmembers4, True, "corrected_4_observables", sampling
    )
    samples = pd.concat([samples3, samples4], ignore_index=True)
    posterior, diagnostics = summarize_samples(samples)
    optimizers = pd.concat([fit3, fit4], ignore_index=True)
    concentrations = pd.concat([concentrations3, concentrations4], ignore_index=True)
    comparison, metrics = compare_fractions(paper, optimizers, posterior)

    reference_chi2 = pd.read_csv(
        prepared.context.paths.reference_results_path, sep="\t"
    )[["Well", "4bin_chi2", "4bin_pchi2"]].rename(
        columns={
            "Well": "well_id",
            "4bin_chi2": "visser_chi2",
            "4bin_pchi2": "visser_pchi2_percent",
        }
    )
    table3 = fit4.merge(reference_chi2, on="well_id", how="left")

    paths = {
        "forward_qualification": output_dir / "forward_convention_qualification.csv",
        "endmembers_3": output_dir / "endmembers_current_3_observables.csv",
        "endmembers_4": output_dir / "endmembers_corrected_4_observables.csv",
        "optimizer": output_dir / "optimizer_summary.csv",
        "concentrations": output_dir / "modeled_vs_observed.csv",
        "samples": output_dir / "mh_samples.csv.gz",
        "posterior": output_dir / "posterior_summary.csv",
        "diagnostics": output_dir / "chain_diagnostics.csv",
        "comparison": output_dir / "fraction_comparison.csv",
        "metrics": output_dir / "global_metrics.csv",
        "table3": output_dir / "visser_table3_reproduction.csv",
        "figure3": output_dir / "figure3_holten_helium_reintroduced.png",
        "figure9": output_dir / "visser_figure9_reproduction.png",
        "figure10b": output_dir / "visser_figure10b_reproduction.png",
        "modeled_observed_figure": output_dir / "modeled_vs_observed.png",
    }
    qualification.to_csv(paths["forward_qualification"], index=False)
    endmembers3.to_csv(paths["endmembers_3"], index=False)
    endmembers4.to_csv(paths["endmembers_4"], index=False)
    optimizers.to_csv(paths["optimizer"], index=False)
    concentrations.to_csv(paths["concentrations"], index=False)
    samples.to_csv(paths["samples"], index=False, compression="gzip")
    posterior.to_csv(paths["posterior"], index=False)
    diagnostics.to_csv(paths["diagnostics"], index=False)
    comparison.to_csv(paths["comparison"], index=False)
    metrics.to_csv(paths["metrics"], index=False)
    table3.to_csv(paths["table3"], index=False)
    plot_new_figure3(comparison, paths["figure3"])
    plot_figure9_reproduction(prepared, convention, endmembers4, paths["figure9"])
    plot_figure10b_reproduction(paper, fit4, paths["figure10b"])
    plot_modeled_observed(concentrations, paths["modeled_observed_figure"])
    generated = list(paths.values())
    paths["manifest"] = write_manifest(
        prepared, output_dir, convention, sampling, generated
    )
    return paths


def main() -> None:
    """Parse command-line settings and run the Holten reproduction."""
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root
        / "results"
        / "article_non_ploemeur_final"
        / "holten"
        / "helium_reproduction",
    )
    parser.add_argument("--nstep", type=int, default=10_000)
    parser.add_argument("--nchains", type=int, default=4)
    parser.add_argument("--burn-in", type=float, default=0.2)
    parser.add_argument("--proposal-scale", type=float, default=0.18)
    parser.add_argument("--seed", type=int, default=12_345)
    args = parser.parse_args()
    config = SamplingConfig(
        nstep=args.nstep,
        burn_in=args.burn_in,
        proposal_scale=args.proposal_scale,
        nchains=args.nchains,
        seed=args.seed,
    )
    paths = run_reproduction(args.output_dir.resolve(), config)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
