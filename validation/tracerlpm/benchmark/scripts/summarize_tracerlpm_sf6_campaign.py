"""Compare the 30-run PyAge and TracerLPM four-tracer campaigns."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import expanded_cases
from .invert_pyage_pilot import RESULT_DIR

CONFIG = BENCHMARK_ROOT / "configs" / "inversion-monte-carlo-01-sf6.yaml"
RUN_OUTPUT = BENCHMARK_ROOT.parent / "output" / "four-tracer"
OUTPUT = BENCHMARK_ROOT / "generated" / "tracerlpm-sf6-monte-carlo"


def _statistics(values: np.ndarray, truth: float) -> dict:
    errors = values - truth
    return {
        "mean": float(np.mean(values)),
        "standard_deviation": float(np.std(values, ddof=1)),
        "bias": float(np.mean(errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "q025": float(np.quantile(values, 0.025)),
        "median": float(np.median(values)),
        "q975": float(np.quantile(values, 0.975)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def _latest_tracerlpm_result(case_id: str) -> Path:
    candidates = sorted(
        RUN_OUTPUT.glob(f"{case_id}-tracerlpm-*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"Résultat TracerLPM absent pour {case_id}")
    return candidates[-1]


def summarize() -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rows = []
    for case in expanded_cases(config):
        pyage_path = RESULT_DIR / case["case_id"] / "pyage-result.json"
        pyage = json.loads(pyage_path.read_text(encoding="utf-8"))
        tracer_path = _latest_tracerlpm_result(case["case_id"])
        tracer = json.loads(tracer_path.read_text(encoding="utf-8-sig"))
        if tracer.get("status") != "success" or not tracer.get("fit"):
            raise ValueError(f"Résultat TracerLPM invalide pour {case['case_id']}")
        secondary_key = "eta" if case["model"] == "EPM" else "DP"
        secondary_offset = 1.0 if case["model"] == "EPM" else 0.0
        rows.append(
            {
                "case_id": case["case_id"],
                "model": case["model"],
                "seed": case["noise"]["seed"],
                "pyage_tau": float(pyage["estimated_parameters"]["tau"]),
                "pyage_secondary": float(pyage["estimated_parameters"][secondary_key])
                - secondary_offset,
                "tracerlpm_tau": float(tracer["fit"]["estimatedAge"]),
                "tracerlpm_secondary": float(tracer["fit"]["estimatedModelParameter"]),
                "tracerlpm_objective": float(tracer["fit"]["objective"]),
                "tracerlpm_report": tracer_path.relative_to(
                    BENCHMARK_ROOT.parent
                ).as_posix(),
            }
        )

    models = {}
    for model in ("EPM", "DM"):
        selected = [row for row in rows if row["model"] == model]
        if len(selected) != 30:
            raise ValueError(f"Campagne {model} incomplète : {len(selected)}/30")
        secondary_name, secondary_truth = ("r", 2.0) if model == "EPM" else ("DP", 0.2)
        p_tau = np.asarray([row["pyage_tau"] for row in selected])
        p_sec = np.asarray([row["pyage_secondary"] for row in selected])
        t_tau = np.asarray([row["tracerlpm_tau"] for row in selected])
        t_sec = np.asarray([row["tracerlpm_secondary"] for row in selected])
        models[model] = {
            "count": len(selected),
            "secondary_name": secondary_name,
            "pyage": {
                "tau": _statistics(p_tau, 20.0),
                "secondary": _statistics(p_sec, secondary_truth),
            },
            "tracerlpm": {
                "tau": _statistics(t_tau, 20.0),
                "secondary": _statistics(t_sec, secondary_truth),
            },
            "paired_tracerlpm_minus_pyage": {
                "tau_mean": float(np.mean(t_tau - p_tau)),
                "tau_rmse": float(np.sqrt(np.mean((t_tau - p_tau) ** 2))),
                "secondary_mean": float(np.mean(t_sec - p_sec)),
                "secondary_rmse": float(np.sqrt(np.mean((t_sec - p_sec) ** 2))),
            },
        }

    summary = {
        "campaign_id": config["campaign_id"],
        "noise_relative_sd": 0.01,
        "tracers": [item["name"] for item in config["tracers"]],
        "models": models,
        "rows": rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with (OUTPUT / "results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Comparaison PyAge–TracerLPM — 30 réalisations, quatre traceurs, bruit 1 %",
        "",
        "Traceurs : CFC-11, CFC-12, CFC-113 et SF6.",
        "",
        "| Modèle | Outil | Paramètre | Vrai | Moyenne | Biais | Écart type | RMSE | q2,5 % | q97,5 % |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model, data in models.items():
        for tool in ("pyage", "tracerlpm"):
            for key, label, truth in (
                ("tau", "tau", 20.0),
                ("secondary", data["secondary_name"], 2.0 if model == "EPM" else 0.2),
            ):
                stats = data[tool][key]
                lines.append(
                    f"| {model} | {tool} | {label} | {truth:.6g} | {stats['mean']:.6g} | "
                    f"{stats['bias']:.6g} | {stats['standard_deviation']:.6g} | {stats['rmse']:.6g} | "
                    f"{stats['q025']:.6g} | {stats['q975']:.6g} |"
                )
    (OUTPUT / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
