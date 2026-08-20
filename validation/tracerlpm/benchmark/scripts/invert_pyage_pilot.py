"""Invert no-noise one- and two-parameter pilots with current PyAge."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable

import numpy as np
import yaml
from scipy.optimize import OptimizeResult, minimize

from pyage.convolution.convolution import Convolution
from pyage.lpm.lpm_build import lpm_build
from pyage.tracer.tracer_root import Tracer

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import (
    DEFAULT_CONFIG,
    OUTPUT_DIR,
    REPO_ROOT,
    expanded_cases,
)

RESULT_DIR = BENCHMARK_ROOT / "generated" / "inversion"
MODEL_NAMES = {"EMM": "exp", "EPM": "exp_shifted", "DM": "ig"}
PARAMETER_NAMES = {"EMM": ["tau"], "EPM": ["tau", "eta"], "DM": ["tau", "DP"]}


def invert(
    config_path: Path = DEFAULT_CONFIG,
    observation_dir: Path = OUTPUT_DIR,
    result_dir: Path = RESULT_DIR,
    case_ids: set[str] | None = None,
) -> dict:
    """Run every selected inversion case and write its detailed result."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    summaries = []
    for case in expanded_cases(config):
        if case_ids is not None and case["case_id"] not in case_ids:
            continue
        if case["model"] not in MODEL_NAMES:
            raise ValueError("Le pilote PyAge accepte EMM, EPM ou DM")
        summary = _invert_case(config, case, observation_dir)
        _write_case_result(summary, result_dir / case["case_id"])
        summaries.append(summary)
    return {"cases": summaries}


def _invert_case(config: dict, case: dict, observation_dir: Path) -> dict:
    observations = _load_observations(observation_dir, case["case_id"])
    tracers = _load_tracers(observations, observation_dir)
    model = lpm_build(MODEL_NAMES[case["model"]])
    date = float(config["observation_year"])
    observed = np.asarray(
        [float(row["observed_concentration"]) for row in observations]
    )
    scales = _objective_scales(config, case, observations, tracers, observed)
    predict = _predictor(case, model, tracers, date, observations)

    def objective(values: np.ndarray) -> float:
        residuals = (predict(values) - observed) / scales
        return float(np.sum(residuals * residuals))

    parameter_names = PARAMETER_NAMES[case["model"]]
    best, attempts, initial_values = _optimize(case, parameter_names, objective)
    rows = _concentration_rows(observations, predict(best.x), scales)
    return _build_summary(case, parameter_names, best, attempts, initial_values, rows)


def _load_observations(observation_dir: Path, case_id: str) -> list[dict]:
    path = observation_dir / f"{case_id}.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _load_tracers(observations: list[dict], observation_dir: Path) -> dict[str, Tracer]:
    tracers = {}
    for row in observations:
        root = (
            observation_dir / "normalized_tracers"
            if row["tracer"] == "cfc12"
            else REPO_ROOT / "data_core" / "data_tracer"
        )
        tracers[row["tracer"]] = Tracer(root, row["tracer"])
    return tracers


def _objective_scales(
    config: dict,
    case: dict,
    observations: list[dict],
    tracers: dict[str, Tracer],
    observed: np.ndarray,
) -> np.ndarray:
    configured = config["objective"]["relative_standard_deviation"]
    relative_std = (
        float(case["noise"]["relative_standard_deviation"])
        if configured == "match_noise"
        else float(configured)
    )
    floor_fraction = float(
        config["objective"]["absolute_floor_fraction_of_tracer_maximum"]
    )
    return np.asarray(
        [
            max(
                relative_std * value,
                floor_fraction * tracers[row["tracer"]].max_value(),
            )
            for row, value in zip(observations, observed)
        ]
    )


def _predictor(
    case: dict,
    model,
    tracers: dict[str, Tracer],
    date: float,
    observations: list[dict],
) -> Callable[[np.ndarray], np.ndarray]:
    def predict(values: np.ndarray | list[float]) -> np.ndarray:
        _configure_model(model, case["model"], values)
        return np.asarray(
            [
                Convolution(tracers[row["tracer"]], date=date).convolve(model)
                for row in observations
            ]
        )

    return predict


def _configure_model(model, model_name: str, values: np.ndarray | list[float]) -> None:
    tau = float(values[0])
    if model_name == "EMM":
        model.p["mu"] = tau
    elif model_name == "EPM":
        eta = float(values[1])
        model.p.update({"mu": tau / eta, "shift": tau * (1.0 - 1.0 / eta)})
    else:
        dp = float(values[1])
        model.p.update({"mu": tau, "sigma": tau * np.sqrt(2.0 * dp)})


def _parameter_space(case: dict, names: list[str]):
    bounds = [tuple(float(value) for value in case["bounds"][name]) for name in names]
    initial_values = (
        [[float(value)] for value in case["initial_values"]["tau"]]
        if case["model"] == "EMM"
        else [[float(value) for value in pair] for pair in case["initial_values"]]
    )
    return bounds, initial_values


def _optimize(
    case: dict, names: list[str], objective: Callable[[np.ndarray], float]
) -> tuple[OptimizeResult, list[OptimizeResult], list[list[float]]]:
    bounds, initial_values = _parameter_space(case, names)
    attempts = [
        _minimize_one(case["model"], initial, bounds, objective)
        for initial in initial_values
    ]
    minimum = min(float(item.fun) for item in attempts)
    tolerance = max(1e-10, abs(minimum) * 1e-6)
    successful = [
        item
        for item in attempts
        if bool(item.success) and float(item.fun) <= minimum + tolerance
    ]
    best = min(successful or attempts, key=lambda item: float(item.fun))
    return best, attempts, initial_values


def _minimize_one(
    model_name: str,
    initial: list[float],
    bounds: list[tuple[float, float]],
    objective: Callable[[np.ndarray], float],
) -> OptimizeResult:
    initial_objective = objective(np.asarray(initial, dtype=float))
    method = "Powell" if model_name == "EPM" else "L-BFGS-B"
    options = (
        {"xtol": 1e-7, "ftol": 1e-10, "maxiter": 2000}
        if method == "Powell"
        else {"ftol": 1e-12, "maxiter": 2000}
    )
    result = minimize(objective, initial, method=method, bounds=bounds, options=options)
    if initial_objective <= float(result.fun):
        return OptimizeResult(
            x=np.asarray(initial, dtype=float),
            fun=initial_objective,
            success=True,
            message="Initial point retained because optimization did not improve it",
        )
    return result


def _concentration_rows(
    observations: list[dict], calculated: np.ndarray, scales: np.ndarray
) -> list[dict]:
    rows = []
    for source, value, scale in zip(observations, calculated, scales):
        observed = float(source["observed_concentration"])
        rows.append(
            {
                "tracer": source["tracer"],
                "observed": observed,
                "calculated": float(value),
                "residual": float(value - observed),
                "normalized_residual": float((value - observed) / scale),
            }
        )
    return rows


def _build_summary(
    case: dict,
    parameter_names: list[str],
    best: OptimizeResult,
    attempts: list[OptimizeResult],
    initial_values: list[list[float]],
    rows: list[dict],
) -> dict:
    estimated = {name: float(value) for name, value in zip(parameter_names, best.x)}
    truth = {name: float(case["true_parameters"][name]) for name in parameter_names}
    true_tau = float(case["true_parameters"]["tau"])
    maximum_relative_error = max(
        abs(row["residual"]) / max(abs(row["observed"]), 1e-300) for row in rows
    )
    return {
        "case_id": case["case_id"],
        "model": case["model"],
        "true_tau": true_tau,
        "estimated_tau": float(best.x[0]),
        "tau_absolute_error": abs(float(best.x[0]) - true_tau),
        "true_parameters": truth,
        "estimated_parameters": estimated,
        "parameter_absolute_errors": {
            name: abs(estimated[name] - truth[name]) for name in parameter_names
        },
        "objective_chi_square": float(best.fun),
        "optimizer_success": bool(best.success),
        "optimizer_message": str(best.message),
        "attempt_count": len(attempts),
        "maximum_recalculated_relative_error": maximum_relative_error,
        "concentrations": rows,
        "attempts": [
            {
                "initial": initial,
                "estimated": [float(value) for value in result.x],
                "objective": float(result.fun),
                "success": bool(result.success),
            }
            for initial, result in zip(initial_values, attempts)
        ],
    }


def _write_case_result(summary: dict, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "pyage-result.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    rows = summary["concentrations"]
    with (target / "pyage-concentrations.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    print(json.dumps(invert(), indent=2))
