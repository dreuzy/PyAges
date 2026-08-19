"""Aggregate parameter distributions from the 30-realization PyAge campaign."""

from __future__ import annotations

import json

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import expanded_cases
from .invert_pyage_pilot import RESULT_DIR


CONFIG = BENCHMARK_ROOT / "configs" / "inversion-monte-carlo-01.yaml"
OUTPUT = BENCHMARK_ROOT / "generated" / "inversion-monte-carlo-01"


def _statistics(values: np.ndarray, truth: float) -> dict:
    errors = values - truth
    return {
        "mean": float(np.mean(values)), "standard_deviation": float(np.std(values, ddof=1)),
        "bias": float(np.mean(errors)), "rmse": float(np.sqrt(np.mean(errors**2))),
        "q025": float(np.quantile(values, 0.025)), "median": float(np.median(values)),
        "q975": float(np.quantile(values, 0.975)), "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def summarize() -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    cases = expanded_cases(config)
    models = {}
    rows = []
    for case in cases:
        result = json.loads((RESULT_DIR / case["case_id"] / "pyage-result.json").read_text(encoding="utf-8"))
        secondary_key = "eta" if case["model"] == "EPM" else "DP"
        secondary = result["estimated_parameters"][secondary_key] - (1.0 if case["model"] == "EPM" else 0.0)
        rows.append({"case_id": case["case_id"], "model": case["model"],
                     "seed": case["noise"]["seed"], "tau": result["estimated_parameters"]["tau"],
                     "secondary": secondary, "success": result["optimizer_success"]})
    for model in ("EPM", "DM"):
        selected = [row for row in rows if row["model"] == model]
        secondary_name, secondary_truth = ("r", 2.0) if model == "EPM" else ("DP", 0.2)
        models[model] = {
            "count": len(selected), "successful": sum(row["success"] for row in selected),
            "tau": _statistics(np.asarray([row["tau"] for row in selected]), 20.0),
            "secondary_name": secondary_name,
            "secondary": _statistics(np.asarray([row["secondary"] for row in selected]), secondary_truth),
        }
    summary = {"campaign_id": config["campaign_id"], "noise_relative_sd": 0.01,
               "models": models, "rows": rows}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = ["# Monte-Carlo PyAge — 30 réalisations à 1 %", "",
             "| Modèle | Paramètre | Vrai | Moyenne | Biais | Écart type | RMSE | q2,5 % | Médiane | q97,5 % |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for model, data in models.items():
        for name, truth, stats in (("tau", 20.0, data["tau"]),
                                   (data["secondary_name"], 2.0 if model == "EPM" else 0.2, data["secondary"])):
            lines.append(f"| {model} | {name} | {truth:.6g} | {stats['mean']:.6g} | {stats['bias']:.6g} | "
                         f"{stats['standard_deviation']:.6g} | {stats['rmse']:.6g} | {stats['q025']:.6g} | "
                         f"{stats['median']:.6g} | {stats['q975']:.6g} |")
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
