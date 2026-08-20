"""Aggregate paired PyAge/TracerLPM results for robustness phases 1 and 3."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import expanded_cases
from .invert_pyage_pilot import RESULT_DIR

CONFIGS = (
    ("width_noise", BENCHMARK_ROOT / "configs" / "robustness-width-noise.yaml"),
    ("age_noise", BENCHMARK_ROOT / "configs" / "robustness-age-noise.yaml"),
)
RUN_OUTPUT = BENCHMARK_ROOT.parent / "output" / "robustness-study"
OUTPUT = BENCHMARK_ROOT / "generated" / "robustness-study"
TRACERLPM_TO_PYAGE = {
    "CFC-11": "cfc11",
    "CFC-12": "cfc12",
    "CFC-113": "cfc113",
    "SF6": "sf6",
}


def _statistics(values: list[float], truth: float) -> dict:
    data = np.asarray(values, dtype=float)
    errors = data - truth
    return {
        "mean": float(np.mean(data)),
        "standard_deviation": float(np.std(data, ddof=1)) if len(data) > 1 else 0.0,
        "bias": float(np.mean(errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "median": float(np.median(data)),
        "q025": float(np.quantile(data, 0.025)),
        "q975": float(np.quantile(data, 0.975)),
        "minimum": float(np.min(data)),
        "maximum": float(np.max(data)),
    }


def _latest_report(case_id: str, run_output: Path = RUN_OUTPUT) -> Path:
    candidates = sorted(
        run_output.glob(f"{case_id}-tracerlpm-*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"Résultat TracerLPM absent pour {case_id}")
    return candidates[-1]


def _maximum_relative_error(observed: dict, calculated: dict) -> float:
    return max(
        abs(float(calculated[name]) - float(value)) / max(abs(float(value)), 1e-300)
        for name, value in observed.items()
    )


def _relative_objectives(observed: dict, calculated: dict) -> tuple[float, float]:
    residuals = [
        abs(float(calculated[name]) - float(value)) / max(abs(float(value)), 1e-300)
        for name, value in observed.items()
    ]
    return float(sum(residuals)), float(sum(value * value for value in residuals))


def _best_calculated_concentrations(fit: dict) -> dict:
    candidates = [
        attempt
        for attempt in fit["attempts"]
        if abs(float(attempt["objective"]) - float(fit["objective"])) <= 1e-10
    ]
    if not candidates:
        raise ValueError("Aucune tentative TracerLPM ne correspond à l'objectif retenu")
    return candidates[0]["calculatedConcentrations"]


def _near_boundary(value: float, bounds: list[float]) -> bool:
    lower, upper = (float(item) for item in bounds)
    tolerance = max(1e-8, (upper - lower) * 1e-5)
    return value <= lower + tolerance or value >= upper - tolerance


def _load_results(case: dict, run_output: Path) -> tuple[dict, dict, Path]:
    pyage_path = RESULT_DIR / case["case_id"] / "pyage-result.json"
    pyage = json.loads(pyage_path.read_text(encoding="utf-8"))
    report_path = _latest_report(case["case_id"], run_output)
    tracer = json.loads(report_path.read_text(encoding="utf-8-sig"))
    fit = tracer.get("fit")
    if tracer.get("status") != "success" or not fit:
        raise ValueError(f"Résultat TracerLPM invalide pour {case['case_id']}")
    return pyage, tracer, report_path


def _paired_observations(pyage: dict, fit: dict, case_id: str) -> tuple[dict, dict]:
    observed = {
        item["tracer"]: float(item["observed"]) for item in pyage["concentrations"]
    }
    calculated = {
        item["tracer"]: float(item["calculated"]) for item in pyage["concentrations"]
    }
    tracer_observed = {
        TRACERLPM_TO_PYAGE[name]: float(value)
        for name, value in fit["observations"].items()
    }
    mismatched = observed.keys() != tracer_observed.keys() or any(
        not np.isclose(value, tracer_observed[name], rtol=0.0, atol=1e-12)
        for name, value in observed.items()
    )
    if mismatched:
        raise ValueError(f"Pseudo-observations non appariées pour {case_id}")
    return observed, calculated


def _case_row(phase: str, case: dict, run_output: Path) -> dict:
    pyage, tracer, report_path = _load_results(case, run_output)
    fit = tracer["fit"]
    epm = case["model"] == "EPM"
    secondary_key = "eta" if epm else "DP"
    offset = 1.0 if epm else 0.0
    secondary_bounds = [
        float(value) - offset for value in case["bounds"][secondary_key]
    ]
    pyage_observed, pyage_calculated = _paired_observations(pyage, fit, case["case_id"])
    tracer_calculated = _best_calculated_concentrations(fit)
    pyage_l1, pyage_l2 = _relative_objectives(pyage_observed, pyage_calculated)
    tracer_l1, tracer_l2 = _relative_objectives(fit["observations"], tracer_calculated)
    pyage_tau = float(pyage["estimated_parameters"]["tau"])
    pyage_secondary = float(pyage["estimated_parameters"][secondary_key]) - offset
    tracer_tau = float(fit["estimatedAge"])
    tracer_secondary = float(fit["estimatedModelParameter"])
    return {
        "phase": phase,
        "case_id": case["case_id"],
        "model": case["model"],
        "seed": int(case["noise"]["seed"]),
        "noise_relative_sd": float(case["noise"]["relative_standard_deviation"]),
        "true_tau": float(case["true_parameters"]["tau"]),
        "secondary_name": "r" if epm else "DP",
        "true_secondary": float(case["true_parameters"][secondary_key]) - offset,
        "tau_lower_bound": float(case["bounds"]["tau"][0]),
        "tau_upper_bound": float(case["bounds"]["tau"][1]),
        "secondary_lower_bound": secondary_bounds[0],
        "secondary_upper_bound": secondary_bounds[1],
        "initial_values_json": json.dumps(case["initial_values"], sort_keys=True),
        "observations_json": json.dumps(pyage_observed, sort_keys=True),
        "pyage_tau": pyage_tau,
        "pyage_secondary": pyage_secondary,
        "pyage_success": bool(pyage["optimizer_success"]),
        "pyage_boundary_hit": _near_boundary(pyage_tau, case["bounds"]["tau"])
        or _near_boundary(pyage_secondary, secondary_bounds),
        "pyage_maximum_concentration_relative_error": float(
            pyage["maximum_recalculated_relative_error"]
        ),
        "pyage_native_weighted_l2_objective": float(pyage["objective_chi_square"]),
        "pyage_recalculated_relative_l1_objective": pyage_l1,
        "pyage_recalculated_relative_l2_objective": pyage_l2,
        "pyage_calculated_concentrations_json": json.dumps(
            pyage_calculated, sort_keys=True
        ),
        "tracerlpm_tau": tracer_tau,
        "tracerlpm_secondary": tracer_secondary,
        "tracerlpm_success": tracer.get("status") == "success",
        "tracerlpm_boundary_hit": _near_boundary(tracer_tau, case["bounds"]["tau"])
        or _near_boundary(tracer_secondary, secondary_bounds),
        "tracerlpm_maximum_concentration_relative_error": _maximum_relative_error(
            fit["observations"], tracer_calculated
        ),
        "tracerlpm_native_l1_objective": float(fit["objective"]),
        "tracerlpm_objective": float(fit["objective"]),
        "tracerlpm_recalculated_relative_l1_objective": tracer_l1,
        "tracerlpm_recalculated_relative_l2_objective": tracer_l2,
        "tracerlpm_calculated_concentrations_json": json.dumps(
            tracer_calculated, sort_keys=True
        ),
        "tracerlpm_report": _relative_report_path(report_path),
    }


def _relative_report_path(path: Path) -> str:
    if path.is_relative_to(BENCHMARK_ROOT.parent):
        return path.relative_to(BENCHMARK_ROOT.parent).as_posix()
    return str(path.resolve())


def _collect_rows(run_output: Path) -> tuple[list[dict], list[str]]:
    rows, campaign_ids = [], []
    for phase, config_path in CONFIGS:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        campaign_ids.append(config["campaign_id"])
        rows.extend(
            _case_row(phase, case, run_output) for case in expanded_cases(config)
        )
    return rows, campaign_ids


def _group_rows(rows: list[dict]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            row["model"],
            row["true_tau"],
            row["secondary_name"],
            row["true_secondary"],
            row["noise_relative_sd"],
        )
        groups[key].append(row)
    return groups


def _tool_statistics(selected: list[dict], tool: str, tau_truth, secondary_truth):
    tau = [float(row[f"{tool}_tau"]) for row in selected]
    secondary = [float(row[f"{tool}_secondary"]) for row in selected]
    errors = [row[f"{tool}_maximum_concentration_relative_error"] for row in selected]
    return {
        "successful": sum(bool(row[f"{tool}_success"]) for row in selected),
        "boundary_hits": sum(bool(row[f"{tool}_boundary_hit"]) for row in selected),
        "tau": _statistics(tau, tau_truth),
        "secondary": _statistics(secondary, secondary_truth),
        "maximum_concentration_relative_error_median": float(np.median(errors)),
    }


def _paired_tool_statistics(selected: list[dict]) -> dict:
    tau_delta = [row["tracerlpm_tau"] - row["pyage_tau"] for row in selected]
    secondary_delta = [
        row["tracerlpm_secondary"] - row["pyage_secondary"] for row in selected
    ]
    return {
        "tau_mean": float(np.mean(tau_delta)),
        "tau_rmse": float(np.sqrt(np.mean(np.square(tau_delta)))),
        "secondary_mean": float(np.mean(secondary_delta)),
        "secondary_rmse": float(np.sqrt(np.mean(np.square(secondary_delta)))),
    }


def _summarize_groups(rows: list[dict]) -> list[dict]:
    summaries = []
    for key, selected in sorted(_group_rows(rows).items()):
        if len(selected) != 10:
            raise ValueError(f"Groupe incomplet {key}: {len(selected)}/10")
        model, tau_truth, secondary_name, secondary_truth, noise = key
        summaries.append(
            {
                "model": model,
                "true_tau": tau_truth,
                "secondary_name": secondary_name,
                "true_secondary": secondary_truth,
                "noise_relative_sd": noise,
                "count": len(selected),
                "tools": {
                    tool: _tool_statistics(selected, tool, tau_truth, secondary_truth)
                    for tool in ("pyage", "tracerlpm")
                },
                "paired_tracerlpm_minus_pyage": _paired_tool_statistics(selected),
            }
        )
    return summaries


def summarize(run_output: Path = RUN_OUTPUT, output: Path = OUTPUT) -> dict:
    """Build paired case and grouped robustness summaries."""
    rows, campaign_ids = _collect_rows(run_output)
    groups = _summarize_groups(rows)
    summary = {
        "campaign_ids": campaign_ids,
        "tracers": ["CFC-11", "CFC-12", "CFC-113", "SF6"],
        "case_count": len(rows),
        "group_count": len(groups),
        "groups": groups,
        "rows": rows,
    }
    _write_outputs(summary, output)
    return summary


def _write_outputs(summary: dict, output: Path) -> None:
    rows, groups = summary["rows"], summary["groups"]
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (output / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output / "summary.md").write_text(
        "\n".join(_markdown_lines(rows, groups)) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _markdown_lines(rows: list[dict], groups: list[dict]) -> list[str]:
    lines = [
        "# Robustesse PyAge–TracerLPM — largeurs, âges et bruit jusqu'à 20 %",
        "",
        f"{len(rows)} inversions appariées avec CFC-11, CFC-12, CFC-113 et SF6.",
        "Aucune combinaison ou suppression de traceur n'est testée.",
        "",
        "| Modèle | tau vrai | Paramètre 2 | Vrai | Bruit | Outil | Succès | Bornes | RMSE tau | RMSE param. 2 | Médiane erreur conc. max |",
        "|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for group in groups:
        for tool in ("pyage", "tracerlpm"):
            stats = group["tools"][tool]
            lines.append(
                f"| {group['model']} | {group['true_tau']:.6g} | {group['secondary_name']} | "
                f"{group['true_secondary']:.6g} | {100 * group['noise_relative_sd']:.0f} % | "
                f"{tool} | {stats['successful']}/{group['count']} | {stats['boundary_hits']} | "
                f"{stats['tau']['rmse']:.6g} | {stats['secondary']['rmse']:.6g} | "
                f"{100 * stats['maximum_concentration_relative_error_median']:.3g} % |"
            )
    return lines


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-output", type=Path, default=RUN_OUTPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = summarize(args.run_output, args.output)
    print(
        json.dumps(
            {"case_count": result["case_count"], "group_count": result["group_count"]},
            indent=2,
        )
    )
