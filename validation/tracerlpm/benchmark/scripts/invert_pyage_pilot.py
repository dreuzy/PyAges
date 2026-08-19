"""Invert no-noise one- and two-parameter pilots with current PyAge."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import OptimizeResult, minimize

from pyage.convolution.convolution import Convolution
from pyage.lpm.lpm_build import lpm_build
from pyage.tracer.tracer_root import Tracer

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import DEFAULT_CONFIG, OUTPUT_DIR, REPO_ROOT, expanded_cases


RESULT_DIR = BENCHMARK_ROOT / "generated" / "inversion"


def invert(config_path: Path = DEFAULT_CONFIG, observation_dir: Path = OUTPUT_DIR,
           result_dir: Path = RESULT_DIR, case_ids: set[str] | None = None) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    summaries = []
    for case in expanded_cases(config):
        if case_ids is not None and case["case_id"] not in case_ids:
            continue
        if case["model"] not in {"EMM", "EPM", "DM"}:
            raise ValueError("Le pilote PyAge accepte EMM, EPM ou DM")
        observation_path = observation_dir / f"{case['case_id']}.csv"
        with observation_path.open(encoding="utf-8", newline="") as stream:
            observations = list(csv.DictReader(stream))
        tracers = {}
        for row in observations:
            tracer_root = (
                observation_dir / "normalized_tracers"
                if row["tracer"] == "cfc12"
                else REPO_ROOT / "data_core" / "data_tracer"
            )
            tracers[row["tracer"]] = Tracer(tracer_root, row["tracer"])
        lpm = lpm_build({"EMM": "exp", "EPM": "exp_shifted", "DM": "ig"}[case["model"]])
        date = float(config["observation_year"])
        configured_relative_std = config["objective"]["relative_standard_deviation"]
        relative_std = (
            float(case["noise"]["relative_standard_deviation"])
            if configured_relative_std == "match_noise"
            else float(configured_relative_std)
        )
        floor_fraction = float(config["objective"]["absolute_floor_fraction_of_tracer_maximum"])
        observed = np.asarray([float(row["observed_concentration"]) for row in observations])
        scales = np.asarray([
            max(relative_std * value, floor_fraction * tracers[row["tracer"]].max_value())
            for row, value in zip(observations, observed)
        ])

        def predict(values: np.ndarray | list[float]) -> np.ndarray:
            tau = float(values[0])
            if case["model"] == "EMM":
                lpm.p["mu"] = tau
            elif case["model"] == "EPM":
                eta = float(values[1])
                lpm.p.update({"mu": tau / eta, "shift": tau * (1.0 - 1.0 / eta)})
            else:
                dp = float(values[1])
                lpm.p.update({"mu": tau, "sigma": tau * np.sqrt(2.0 * dp)})
            return np.asarray([
                Convolution(tracers[row["tracer"]], date=date).convolve(lpm)
                for row in observations
            ])

        def objective(values: np.ndarray) -> float:
            residuals = (predict(values) - observed) / scales
            return float(np.sum(residuals * residuals))

        parameter_names = {
            "EMM": ["tau"], "EPM": ["tau", "eta"], "DM": ["tau", "DP"]
        }[case["model"]]
        bounds = [tuple(float(value) for value in case["bounds"][name]) for name in parameter_names]
        initial_values = (
            [[float(value)] for value in case["initial_values"]["tau"]]
            if case["model"] == "EMM"
            else [[float(value) for value in pair] for pair in case["initial_values"]]
        )
        attempts = []
        for initial in initial_values:
            initial_objective = objective(np.asarray(initial, dtype=float))
            # EPM needs a derivative-free search on the discrete production
            # convolution. DM is smoother and converges more reliably with
            # bounded L-BFGS-B.
            method = "Powell" if case["model"] == "EPM" else "L-BFGS-B"
            result = minimize(
                objective, initial, method=method, bounds=bounds,
                options=({"xtol": 1e-7, "ftol": 1e-10, "maxiter": 2000}
                         if method == "Powell" else {"ftol": 1e-12, "maxiter": 2000}),
            )
            if initial_objective <= float(result.fun):
                result = OptimizeResult(
                    x=np.asarray(initial, dtype=float), fun=initial_objective, success=True,
                    message="Initial point retained because optimization did not improve it",
                )
            attempts.append(result)
        minimum_objective = min(float(item.fun) for item in attempts)
        objective_tolerance = max(1e-10, abs(minimum_objective) * 1e-6)
        successful_near_best = [
            item for item in attempts
            if bool(item.success) and float(item.fun) <= minimum_objective + objective_tolerance
        ]
        best = min(successful_near_best or attempts, key=lambda item: float(item.fun))
        estimated_tau = float(best.x[0])
        estimated_parameters = {name: float(value) for name, value in zip(parameter_names, best.x)}
        true_parameters = {name: float(case["true_parameters"][name]) for name in parameter_names}
        calculated = predict(best.x)
        true_tau = float(case["true_parameters"]["tau"])
        rows = []
        for source, calc, scale in zip(observations, calculated, scales):
            obs = float(source["observed_concentration"])
            rows.append({
                "tracer": source["tracer"], "observed": obs, "calculated": float(calc),
                "residual": float(calc - obs), "normalized_residual": float((calc - obs) / scale),
            })
        maximum_relative_error = max(abs(row["residual"]) / max(abs(row["observed"]), 1e-300) for row in rows)
        summary = {
            "case_id": case["case_id"], "model": case["model"],
            "true_tau": true_tau, "estimated_tau": estimated_tau,
            "tau_absolute_error": abs(estimated_tau - true_tau),
            "true_parameters": true_parameters,
            "estimated_parameters": estimated_parameters,
            "parameter_absolute_errors": {
                name: abs(estimated_parameters[name] - true_parameters[name]) for name in parameter_names
            },
            "objective_chi_square": float(best.fun), "optimizer_success": bool(best.success),
            "optimizer_message": str(best.message), "attempt_count": len(attempts),
            "maximum_recalculated_relative_error": maximum_relative_error,
            "concentrations": rows,
            "attempts": [
                {"initial": initial, "estimated": [float(value) for value in result.x],
                 "objective": float(result.fun), "success": bool(result.success)}
                for initial, result in zip(initial_values, attempts)
            ],
        }
        target = result_dir / case["case_id"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "pyage-result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        with (target / "pyage-concentrations.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        summaries.append(summary)
    return {"cases": summaries}


if __name__ == "__main__":
    print(json.dumps(invert(), indent=2))
