# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Holten-specific local 4-bin fitting utilities.

This module implements a benchmark-oriented discrete age-distribution fit
for the Holten example, using the article-like bins:
0-20 years, 20-40 years, 40-60 years, and an old fraction (>60 years).

The implementation is intentionally local to the example because the old
end-member is tracer-specific and should not yet be pushed into the generic
PyAges LPM stack.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from examples.natural.holten.holten_benchmark import build_reference_curve
from examples.natural.holten.holten_case import (
    PreparedHoltenCase,
    build_context,
    load_yaml,
    tracer_yaml_path,
)
from examples.natural.holten.holten_four_bin_plots import (
    plot_fraction_bars,
    plot_fraction_interval_comparison,
    plot_fraction_posteriors,
    plot_modeled_vs_observed,
)
from pyages.tracer.decay import rate_from_config

BIN_DEFINITIONS = (
    {
        "name": "f_0_20",
        "label": "0-20",
        "age_min": 0.0,
        "age_max": 20.0,
        "representative_age": 10.0,
    },
    {
        "name": "f_20_40",
        "label": "20-40",
        "age_min": 20.0,
        "age_max": 40.0,
        "representative_age": 30.0,
    },
    {
        "name": "f_40_60",
        "label": "40-60",
        "age_min": 40.0,
        "age_max": 60.0,
        "representative_age": 50.0,
    },
    {
        "name": "f_old",
        "label": ">60",
        "age_min": 60.0,
        "age_max": np.inf,
        "representative_age": 310.0,
    },
)
BIN_ORDER = [item["name"] for item in BIN_DEFINITIONS]
FRACTION_COLUMNS = BIN_ORDER
LOCAL_4BIN_TRACER_ORDER = ("3H", "kr85", "39Ar")
LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM = ("3H", "3He_trit", "kr85", "39Ar")


def _reference_year(prepared: PreparedHoltenCase) -> float:
    return float(prepared.observed_aggregated["date"].median())


def tritium_parent_daughter(
    initial_tritium: float | np.ndarray,
    age_years: float | np.ndarray,
    *,
    half_life_years: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return conserved 3H and tritiogenic-3He concentrations for Holten.

    ``initial_tritium`` is the effective saturated-zone input in TU.  The
    daughter result is therefore in equivalent TU and deliberately excludes
    atmospheric, terrigenic, and radiogenic helium, which have already been
    removed from Visser's ``3He_trit_TU`` observations.
    """

    if half_life_years <= 0.0:
        raise ValueError("Tritium half-life must be positive")
    initial = np.asarray(initial_tritium, dtype=float)
    ages = np.asarray(age_years, dtype=float)
    if np.any(ages < 0.0):
        raise ValueError("Transit ages must be non-negative")
    decay_rate = np.log(2.0) / float(half_life_years)
    parent = initial * np.exp(-decay_rate * ages)
    daughter = initial * (1.0 - np.exp(-decay_rate * ages))
    return parent, daughter


def _local_4bin_observations(
    prepared: PreparedHoltenCase,
    well_id: str,
    *,
    include_helium: bool = False,
) -> pd.DataFrame:
    obs = prepared.observed_by_well[well_id].copy()
    tracer_order = LOCAL_4BIN_TRACER_ORDER
    if include_helium:
        helium = prepared.helium_diagnostics.loc[
            prepared.helium_diagnostics["well_id"] == well_id
        ]
        if helium.empty:
            raise ValueError(f"Missing helium diagnostics for well {well_id}")
        helium_row = helium.iloc[0]
        if pd.isna(helium_row["3He_trit_TU"]) or pd.isna(helium_row["3He_err"]):
            raise ValueError(
                f"Missing 3He_trit observation or uncertainty for well {well_id}"
            )
        obs = pd.concat(
            [
                obs,
                pd.DataFrame(
                    [
                        {
                            "element": "3He_trit",
                            "concentration": float(helium_row["3He_trit_TU"]),
                            "error": float(helium_row["3He_err"]),
                            "unit": "TU_equivalent",
                            "date": float(helium_row["date"]),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        tracer_order = LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM

    order_map = {name: idx for idx, name in enumerate(tracer_order)}
    obs["_local_order"] = obs["element"].map(order_map)
    if obs["_local_order"].isna().any():
        unknown = sorted(
            obs.loc[obs["_local_order"].isna(), "element"].astype(str).unique()
        )
        raise ValueError(
            f"Unsupported local 4-bin tracer(s) for well {well_id}: {unknown}"
        )
    obs = (
        obs.sort_values(["_local_order", "date"])
        .drop(columns="_local_order")
        .reset_index(drop=True)
    )
    return obs


def _tritium_input_value(
    raw_history: pd.DataFrame,
    tracer_cfg: dict[str, Any],
    recharge_year: np.ndarray,
) -> np.ndarray:
    recharge_year = np.asarray(recharge_year, dtype=float)
    dates = raw_history["date"].astype(float).to_numpy()
    values = raw_history["concentration"].astype(float).to_numpy()
    interp = np.interp(recharge_year, dates, values, left=np.nan, right=values[-1])

    missing = np.isnan(interp)
    if missing.any():
        premodern = float(tracer_cfg["holten"]["premodern_input"]["value"])
        interp[missing] = premodern
    return interp


def _old_endmember_value(
    prepared: PreparedHoltenCase, tracer_name: str, reference_year: float
) -> float:
    tracer_cfg = load_yaml(tracer_yaml_path(prepared.context, tracer_name))
    holten_cfg = tracer_cfg["holten"]
    if tracer_name == "39Ar":
        return float(holten_cfg["old_endmember"]["value"])
    if tracer_name == "kr85":
        return float(holten_cfg["old_endmember"]["value"])
    if tracer_name == "3H":
        premodern = float(holten_cfg["premodern_input"]["value"])
        decay_rate = rate_from_config(tracer_cfg)
        assert decay_rate is not None
        # The old bin starts at >60 years. Using 60 years gives a conservative
        # upper estimate for present-day tritium in the old fraction, and the
        # resulting value is already extremely close to zero.
        age_years = max(60.0, reference_year - 1953.0)
        return float(premodern * np.exp(-decay_rate * age_years))
    raise ValueError(f"Unsupported tracer for Holten 4-bin fit: {tracer_name}")


def _old_endmember_3he_trit(
    prepared: PreparedHoltenCase, reference_year: float
) -> float:
    tracer_cfg = load_yaml(tracer_yaml_path(prepared.context, "3H"))
    premodern = float(tracer_cfg["holten"]["premodern_input"]["value"])
    decay_rate = rate_from_config(tracer_cfg)
    assert decay_rate is not None
    age_years = max(60.0, reference_year - 1953.0)
    return float(premodern * (1.0 - np.exp(-decay_rate * age_years)))


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
        decay_rate = rate_from_config(tracer_cfg)
        assert decay_rate is not None
        if tracer_name == "3H":
            premodern = float(tracer_cfg["holten"]["premodern_input"]["value"])
            ages = reference_year - recharge_year[missing]
            interp[missing] = premodern * np.exp(-decay_rate * ages)
        elif tracer_name == "kr85":
            interp[missing] = float(tracer_cfg["holten"]["old_endmember"]["value"])
        elif tracer_name == "39Ar":
            interp[missing] = values[0]
        else:
            raise ValueError(
                f"Unsupported tracer for interpolation fallback: {tracer_name}"
            )
    return interp


def build_4bin_endmembers(
    prepared: PreparedHoltenCase,
    *,
    include_helium: bool = False,
) -> pd.DataFrame:
    """Build tracer concentrations for the four study-specific age bins.

    Young bins integrate each atmospheric history over its age interval. The
    open old bin uses the tracer-specific convention documented by the Holten
    benchmark, which is why this calculation remains local to the example.
    """
    reference_year = _reference_year(prepared)
    rows: list[dict[str, Any]] = []

    for tracer_name, raw_history in prepared.tracer_histories.items():
        observed = prepared.observed_aggregated.loc[
            prepared.observed_aggregated["element"] == tracer_name
        ].copy()
        display_history = build_reference_curve(
            prepared, tracer_name, raw_history, observed
        )
        tracer_cfg = load_yaml(tracer_yaml_path(prepared.context, tracer_name))
        unit = str(display_history["unit"].iloc[0])

        for spec in BIN_DEFINITIONS[:-1]:
            age_min = float(spec["age_min"])
            age_max = float(spec["age_max"])
            lower_date = reference_year - age_max
            upper_date = reference_year - age_min
            sample_dates = np.linspace(lower_date, upper_date, 120)
            sample_values = _reference_curve_value(
                tracer_name, tracer_cfg, display_history, reference_year, sample_dates
            )
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
                "concentration": _old_endmember_value(
                    prepared, tracer_name, reference_year
                ),
                "unit": unit,
            }
        )

    if include_helium:
        tritium_history = prepared.tracer_histories["3H"]
        tritium_cfg = load_yaml(tracer_yaml_path(prepared.context, "3H"))
        half_life = float(tritium_cfg["half_life"])
        for spec in BIN_DEFINITIONS[:-1]:
            ages = np.linspace(float(spec["age_min"]), float(spec["age_max"]), 120)
            recharge_years = reference_year - ages
            initial = _tritium_input_value(
                tritium_history,
                tritium_cfg,
                recharge_years,
            )
            _, daughter = tritium_parent_daughter(
                initial,
                ages,
                half_life_years=half_life,
            )
            rows.append(
                {
                    "tracer": "3He_trit",
                    "bin_name": spec["name"],
                    "bin_label": spec["label"],
                    "age_min": spec["age_min"],
                    "age_max": spec["age_max"],
                    "representative_age": spec["representative_age"],
                    "concentration": float(np.mean(daughter)),
                    "unit": "TU_equivalent",
                }
            )

        tritium_cfg_holten = tritium_cfg["holten"]
        old_initial = float(tritium_cfg_holten["premodern_input"]["value"])
        old_age = max(60.0, reference_year - 1953.0)
        _, old_daughter = tritium_parent_daughter(
            old_initial,
            old_age,
            half_life_years=half_life,
        )
        old_spec = BIN_DEFINITIONS[-1]
        rows.append(
            {
                "tracer": "3He_trit",
                "bin_name": old_spec["name"],
                "bin_label": old_spec["label"],
                "age_min": old_spec["age_min"],
                "age_max": np.nan,
                "representative_age": old_spec["representative_age"],
                "concentration": float(old_daughter),
                "unit": "TU_equivalent",
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


def _fractions_array(fractions: dict[str, float]) -> np.ndarray:
    return np.asarray([fractions[name] for name in BIN_ORDER], dtype=float)


def _mean_age_local_4bin(fractions: dict[str, float]) -> float:
    return float(
        sum(
            fractions[name] * spec["representative_age"]
            for name, spec in zip(BIN_ORDER, BIN_DEFINITIONS, strict=False)
        )
    )


def _modeled_concentrations(
    matrix: np.ndarray, fractions: dict[str, float]
) -> np.ndarray:
    return matrix @ _fractions_array(fractions)


def _endmember_matrix(endmembers: pd.DataFrame, tracer_order: list[str]) -> np.ndarray:
    matrix = np.zeros((len(tracer_order), len(BIN_ORDER)), dtype=float)
    for i, tracer_name in enumerate(tracer_order):
        subset = endmembers.loc[endmembers["tracer"] == tracer_name].copy()
        subset = subset.set_index("bin_name").loc[BIN_ORDER]
        matrix[i, :] = subset["concentration"].to_numpy(dtype=float)
    return matrix


def _objective_from_matrix(
    matrix: np.ndarray, y: np.ndarray, sigma: np.ndarray, z: np.ndarray
) -> float:
    fractions = _stick_breaking_fractions(z)
    residual = (_modeled_concentrations(matrix, fractions) - y) / sigma
    return float(np.sum(residual * residual))


def _optimize_well_4bin(
    obs: pd.DataFrame, endmembers: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str], Any]:
    tracer_order = obs["element"].tolist()
    y = obs["concentration"].to_numpy(dtype=float)
    sigma = obs["error"].to_numpy(dtype=float)
    matrix = _endmember_matrix(endmembers, tracer_order)

    starts = (
        np.zeros(3, dtype=float),
        np.array([1.0, 0.0, 0.0], dtype=float),
        np.array([-1.0, 0.5, 0.0], dtype=float),
    )

    def objective(z):
        return _objective_from_matrix(matrix, y, sigma, z)

    candidates: list[Any] = []
    for method in ("BFGS", "L-BFGS-B"):
        for start in starts:
            result = minimize(objective, x0=start, method=method)
            candidates.append(result)

    if candidates:
        refined_start = min(candidates, key=lambda result: float(result.fun)).x
        candidates.append(minimize(objective, x0=refined_start, method="Powell"))

    successful = [result for result in candidates if bool(result.success)]
    best = (
        min(successful, key=lambda result: float(result.fun))
        if successful
        else min(
            candidates,
            key=lambda result: float(result.fun),
        )
    )

    assert best is not None
    return matrix, y, sigma, best.x, tracer_order, best


def fit_well_4bin(
    prepared: PreparedHoltenCase,
    well_id: str,
    endmembers: pd.DataFrame,
    *,
    include_helium: bool = False,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Fit constrained age fractions and residuals for one Holten well."""
    obs = _local_4bin_observations(prepared, well_id, include_helium=include_helium)
    matrix, y, sigma, z_opt, tracer_order, best = _optimize_well_4bin(obs, endmembers)
    fractions = _stick_breaking_fractions(z_opt)
    modeled = _modeled_concentrations(matrix, fractions)
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
        "n_observations_local_4bin": int(len(obs)),
        "tracers_local_4bin": ",".join(tracer_order),
        **fractions,
        "chi2_local_4bin": float(np.sum(weighted_residual * weighted_residual)),
        "rmse_local_4bin": float(np.sqrt(np.mean(residual * residual))),
        "weighted_rmse_local_4bin": float(
            np.sqrt(np.mean(weighted_residual * weighted_residual))
        ),
        "mean_age_local_4bin": _mean_age_local_4bin(fractions),
        "optimization_success": bool(best.success),
        "optimization_message": str(best.message),
    }
    return summary, pd.DataFrame(fit_rows)


def fit_all_wells_4bin(
    prepared: PreparedHoltenCase,
    *,
    include_helium: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build end-members and fit all wells selected by the prepared case."""
    endmembers = build_4bin_endmembers(prepared, include_helium=include_helium)
    summary_rows: list[dict[str, Any]] = []
    fit_frames: list[pd.DataFrame] = []
    for well_id in prepared.context.selected_wells:
        summary, fit_frame = fit_well_4bin(
            prepared,
            well_id,
            endmembers,
            include_helium=include_helium,
        )
        summary_rows.append(summary)
        fit_frames.append(fit_frame)
    summary_df = pd.DataFrame(summary_rows)
    fit_df = pd.concat(fit_frames, ignore_index=True)
    return endmembers, summary_df, fit_df


def _read_holten_reference_excel(xlsx_path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(xlsx_path, sheet_name=sheet_name)
    except ImportError as exc:
        raise ImportError(
            "Reading Holten reference Excel data requires the optional dependency "
            "'openpyxl'. Install it in the active environment, for example with "
            "'pip install openpyxl' or by recreating the Conda env from "
            "'install/environment.yml'."
        ) from exc


def _load_shape_free_reference_table(prepared: PreparedHoltenCase) -> pd.DataFrame:
    csv_path = prepared.context.paths.doc_dir / "visser_shape_free_models.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)

    xlsx_path = prepared.context.paths.doc_dir / "visser_data.xlsx"
    return _read_holten_reference_excel(xlsx_path, sheet_name="Shape-free_models")


def _extract_4bin_cumulative(raw_table: pd.DataFrame) -> pd.DataFrame:
    if "model" in raw_table.columns:
        return (
            raw_table.loc[raw_table["model"].astype(str) == "4-bins"]
            .drop(columns=["model"])
            .set_index("age")
            .sort_index()
        )

    age_col = raw_table.columns[1]
    current_model = None
    model_rows: list[dict[str, Any]] = []
    for _, row in raw_table.iterrows():
        label = row.iloc[0]
        if isinstance(label, str) and label.strip():
            current_model = label.strip()
        age_value = row[age_col]
        if (
            current_model == "4-bins"
            and pd.notna(age_value)
            and str(age_value).strip() != "Age"
        ):
            model_rows.append(
                {
                    "age": float(age_value),
                    **{
                        str(col): float(row[col])
                        for col in raw_table.columns[2:]
                        if pd.notna(row[col])
                    },
                }
            )
    return pd.DataFrame(model_rows).set_index("age").sort_index()


def _paper_fraction_row(cumulative: pd.DataFrame, well_id: str) -> dict[str, Any]:
    c0 = float(cumulative.loc[0.0, well_id])
    c20 = float(cumulative.loc[20.0, well_id])
    c40 = float(cumulative.loc[40.0, well_id])
    c60 = float(cumulative.loc[60.0, well_id])
    return {
        "well_id": well_id,
        "f_0_20": c20 - c0,
        "f_20_40": c40 - c20,
        "f_40_60": c60 - c40,
        "f_old": 1.0 - c60,
    }


def load_paper_4bin_fractions(prepared: PreparedHoltenCase) -> pd.DataFrame:
    """Read the Visser cumulative curves and convert them to bin fractions."""
    raw_table = _load_shape_free_reference_table(prepared)
    cumulative = _extract_4bin_cumulative(raw_table)

    rows = [
        _paper_fraction_row(cumulative, well_id)
        for well_id in prepared.context.selected_wells
    ]
    return pd.DataFrame(rows)


def sample_well_4bin_mh(
    prepared: PreparedHoltenCase,
    well_id: str,
    endmembers: pd.DataFrame,
    nstep: int = 4000,
    burn_in: float = 0.2,
    proposal_scale: float = 0.18,
    seed: int = 12345,
    include_helium: bool = False,
) -> pd.DataFrame:
    """Sample one well's four-bin likelihood with a local random-walk MH chain."""
    obs = _local_4bin_observations(prepared, well_id, include_helium=include_helium)
    matrix, y, sigma, z_current, tracer_order, best = _optimize_well_4bin(
        obs, endmembers
    )
    current_obj = float(best.fun)
    rng = np.random.default_rng(seed)
    burn_count = int(nstep * burn_in)
    records: list[dict[str, Any]] = []
    accepted = 0

    for step in range(nstep):
        proposal = z_current + rng.normal(scale=proposal_scale, size=len(z_current))
        proposal_obj = _objective_from_matrix(matrix, y, sigma, proposal)
        log_alpha = -0.5 * (proposal_obj - current_obj)
        accepted_step = False
        if np.log(rng.random()) < min(0.0, log_alpha):
            z_current = proposal
            current_obj = proposal_obj
            accepted += 1
            accepted_step = True

        if step >= burn_count:
            fractions = _stick_breaking_fractions(z_current)
            modeled = _modeled_concentrations(matrix, fractions)
            record = {
                "well_id": well_id,
                "step": step,
                "accepted_step": accepted_step,
                "acceptance_rate_running": accepted / (step + 1),
                "chi2_local_4bin": current_obj,
                "mean_age_local_4bin": _mean_age_local_4bin(fractions),
                **fractions,
            }
            for tracer_name, modeled_value, observed_value, sigma_value in zip(
                tracer_order, modeled, y, sigma, strict=False
            ):
                record[f"{tracer_name}_modeled"] = float(modeled_value)
                record[f"{tracer_name}_observed"] = float(observed_value)
                record[f"{tracer_name}_error"] = float(sigma_value)
            records.append(record)

    return pd.DataFrame(records)


def sample_all_wells_4bin_mh(
    prepared: PreparedHoltenCase,
    endmembers: pd.DataFrame,
    nstep: int = 4000,
    burn_in: float = 0.2,
    proposal_scale: float = 0.18,
    seed: int = 12345,
    include_helium: bool = False,
) -> pd.DataFrame:
    """Sample every selected well with reproducibly derived random seeds."""
    frames: list[pd.DataFrame] = []
    for idx, well_id in enumerate(prepared.context.selected_wells):
        frames.append(
            sample_well_4bin_mh(
                prepared,
                well_id,
                endmembers,
                nstep=nstep,
                burn_in=burn_in,
                proposal_scale=proposal_scale,
                seed=seed + 101 * idx,
                include_helium=include_helium,
            )
        )
    return pd.concat(frames, ignore_index=True)


def summarize_4bin_mh_posterior(samples: pd.DataFrame) -> pd.DataFrame:
    """Compute posterior quantiles for fractions, age, and objective values."""
    rows: list[dict[str, Any]] = []
    summary_cols = [*FRACTION_COLUMNS, "mean_age_local_4bin", "chi2_local_4bin"]
    for well_id, group in samples.groupby("well_id"):
        row: dict[str, Any] = {
            "well_id": well_id,
            "nsamples": int(len(group)),
            "acceptance_rate_mean": float(group["acceptance_rate_running"].iloc[-1]),
        }
        for col in summary_cols:
            series = group[col].astype(float)
            row[f"{col}_mean"] = float(series.mean())
            row[f"{col}_std"] = float(series.std())
            row[f"{col}_q10"] = float(series.quantile(0.10))
            row[f"{col}_q25"] = float(series.quantile(0.25))
            row[f"{col}_median"] = float(series.quantile(0.50))
            row[f"{col}_q75"] = float(series.quantile(0.75))
            row[f"{col}_q90"] = float(series.quantile(0.90))
        rows.append(row)
    return pd.DataFrame(rows)


def compare_paper_vs_mh_4bin(
    paper: pd.DataFrame, posterior: pd.DataFrame
) -> pd.DataFrame:
    """Align paper fractions with local posterior medians and intervals."""
    merged = paper.merge(posterior, on="well_id", how="inner")
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        out = {"well_id": row["well_id"]}
        for frac in FRACTION_COLUMNS:
            out[f"{frac}_paper"] = float(row[frac])
            out[f"{frac}_posterior_median"] = float(row[f"{frac}_median"])
            out[f"{frac}_posterior_q10"] = float(row[f"{frac}_q10"])
            out[f"{frac}_posterior_q90"] = float(row[f"{frac}_q90"])
        rows.append(out)
    return pd.DataFrame(rows)


def write_4bin_outputs(
    endmembers: pd.DataFrame,
    summary: pd.DataFrame,
    fit_df: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    """Write deterministic-fit tables and their two diagnostic figures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    endmembers_path = output_dir / "holten_4bin_endmembers.csv"
    summary_path = output_dir / "holten_4bin_summary.csv"
    fit_path = output_dir / "holten_4bin_modeled_vs_observed.csv"
    endmembers.to_csv(endmembers_path, index=False)
    summary.to_csv(summary_path, index=False)
    fit_df.to_csv(fit_path, index=False)
    fraction_plot = plot_fraction_bars(summary, output_dir)
    fit_plot = plot_modeled_vs_observed(fit_df, output_dir)
    return {
        "endmembers": endmembers_path,
        "summary": summary_path,
        "fit": fit_path,
        "fractions_plot": fraction_plot,
        "fit_plot": fit_plot,
    }


def write_4bin_mh_outputs(
    paper: pd.DataFrame,
    samples: pd.DataFrame,
    posterior: pd.DataFrame,
    comparison: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    """Write posterior tables and figures for comparison with the paper."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paper_path = output_dir / "holten_4bin_paper_reference.csv"
    samples_path = output_dir / "holten_4bin_mh_samples.csv"
    posterior_path = output_dir / "holten_4bin_mh_summary.csv"
    comparison_path = output_dir / "holten_4bin_paper_vs_mh.csv"
    paper.to_csv(paper_path, index=False)
    samples.to_csv(samples_path, index=False)
    posterior.to_csv(posterior_path, index=False)
    comparison.to_csv(comparison_path, index=False)
    posterior_plot = plot_fraction_posteriors(samples, paper, output_dir)
    comparison_plot = plot_fraction_interval_comparison(comparison, output_dir)
    return {
        "paper_reference": paper_path,
        "mh_samples": samples_path,
        "mh_summary": posterior_path,
        "paper_vs_mh": comparison_path,
        "posterior_plot": posterior_plot,
        "comparison_plot": comparison_plot,
    }


def run_local_4bin(
    prepared: PreparedHoltenCase,
    output_dir: Path,
    *,
    include_helium: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    """Run and persist the optimizer-based local four-bin benchmark."""
    endmembers, summary, fit_df = fit_all_wells_4bin(
        prepared,
        include_helium=include_helium,
    )
    paths = write_4bin_outputs(endmembers, summary, fit_df, output_dir)
    return endmembers, summary, fit_df, paths


def run_local_4bin_mh(
    prepared: PreparedHoltenCase,
    output_dir: Path,
    nstep: int = 4000,
    burn_in: float = 0.2,
    proposal_scale: float = 0.18,
    seed: int = 12345,
    include_helium: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    """Run and persist the sampling-based local four-bin benchmark."""
    endmembers = build_4bin_endmembers(prepared, include_helium=include_helium)
    paper = load_paper_4bin_fractions(prepared)
    samples = sample_all_wells_4bin_mh(
        prepared,
        endmembers,
        nstep=nstep,
        burn_in=burn_in,
        proposal_scale=proposal_scale,
        seed=seed,
        include_helium=include_helium,
    )
    posterior = summarize_4bin_mh_posterior(samples)
    comparison = compare_paper_vs_mh_4bin(paper, posterior)
    paths = write_4bin_mh_outputs(paper, samples, posterior, comparison, output_dir)
    return paper, posterior, comparison, paths


if __name__ == "__main__":
    ctx = build_context()
    raise SystemExit(
        f"Holten local 4-bin utilities are available for {ctx.paths.example_dir}"
    )
