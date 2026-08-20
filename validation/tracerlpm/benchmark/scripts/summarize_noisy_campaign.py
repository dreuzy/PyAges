"""Summarize noisy PyAge inversions and, when available, TracerLPM runs."""

from __future__ import annotations

import json
import shutil

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .invert_pyage_pilot import RESULT_DIR

CONFIG = BENCHMARK_ROOT / "configs" / "inversion-noisy-campaign.yaml"
OUTPUT = BENCHMARK_ROOT / "generated" / "inversion-noisy-campaign"
RUN_OUTPUT = BENCHMARK_ROOT.parent / "output"


def summarize() -> dict:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rows = []
    for case in config["cases"]:
        result = json.loads(
            (RESULT_DIR / case["case_id"] / "pyage-result.json").read_text(
                encoding="utf-8"
            )
        )
        secondary = "eta" if case["model"] == "EPM" else "DP"
        true_secondary = float(case["true_parameters"][secondary])
        estimated_secondary = float(result["estimated_parameters"][secondary])
        run_files = sorted(
            RUN_OUTPUT.glob(f"{case['case_id']}-tracerlpm-*.json"),
            key=lambda path: path.stat().st_mtime,
        )
        tracer = (
            json.loads(run_files[-1].read_text(encoding="utf-8-sig"))
            if run_files
            else None
        )
        tracer_fit = tracer.get("fit") if tracer else None
        archived_report = None
        if run_files:
            archive_dir = BENCHMARK_ROOT / "tracerlpm_exports_raw"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archived_report = archive_dir / run_files[-1].name
            shutil.copy2(run_files[-1], archived_report)
        row = {
            "case_id": case["case_id"],
            "model": case["model"],
            "seed": case["noise"]["seed"],
            "tau": result["estimated_parameters"]["tau"],
            "tau_error": result["estimated_parameters"]["tau"]
            - case["true_parameters"]["tau"],
            "secondary_name": "r" if case["model"] == "EPM" else "DP",
            "secondary": estimated_secondary - 1.0
            if case["model"] == "EPM"
            else estimated_secondary,
            "secondary_error": estimated_secondary - true_secondary,
            "objective": result["objective_chi_square"],
            "success": result["optimizer_success"],
            "tracerlpm_report": archived_report.relative_to(BENCHMARK_ROOT).as_posix()
            if archived_report
            else None,
            "tracerlpm_tau": tracer_fit["estimatedAge"] if tracer_fit else None,
            "tracerlpm_secondary": tracer_fit["estimatedModelParameter"]
            if tracer_fit
            else None,
            "tracerlpm_objective": tracer_fit["objective"] if tracer_fit else None,
        }
        if row["tracerlpm_tau"] is not None:
            row["tracerlpm_tau_error"] = (
                row["tracerlpm_tau"] - case["true_parameters"]["tau"]
            )
            tracer_true_secondary = (
                float(case["true_parameters"]["eta"] - 1.0)
                if case["model"] == "EPM"
                else true_secondary
            )
            row["tracerlpm_secondary_error"] = (
                row["tracerlpm_secondary"] - tracer_true_secondary
            )
        rows.append(row)
    models = {}
    for model in ("EPM", "DM"):
        selected = [row for row in rows if row["model"] == model]
        tau_errors = np.asarray([row["tau_error"] for row in selected])
        secondary_errors = np.asarray([row["secondary_error"] for row in selected])
        tracer_selected = [row for row in selected if row["tracerlpm_tau"] is not None]
        tracer_tau_errors = np.asarray(
            [row["tracerlpm_tau_error"] for row in tracer_selected]
        )
        tracer_secondary_errors = np.asarray(
            [row["tracerlpm_secondary_error"] for row in tracer_selected]
        )
        pair_tau = np.asarray(
            [row["tracerlpm_tau"] - row["tau"] for row in tracer_selected]
        )
        pair_secondary = np.asarray(
            [row["tracerlpm_secondary"] - row["secondary"] for row in tracer_selected]
        )
        models[model] = {
            "count": len(selected),
            "successful": sum(row["success"] for row in selected),
            "tau_mean": float(np.mean([row["tau"] for row in selected])),
            "tau_bias": float(np.mean(tau_errors)),
            "tau_rmse": float(np.sqrt(np.mean(tau_errors**2))),
            "secondary_name": selected[0]["secondary_name"],
            "secondary_mean": float(np.mean([row["secondary"] for row in selected])),
            "secondary_bias": float(np.mean(secondary_errors)),
            "secondary_rmse": float(np.sqrt(np.mean(secondary_errors**2))),
            "tracerlpm_count": len(tracer_selected),
            "tracerlpm_tau_mean": float(
                np.mean([row["tracerlpm_tau"] for row in tracer_selected])
            ),
            "tracerlpm_tau_bias": float(np.mean(tracer_tau_errors)),
            "tracerlpm_tau_rmse": float(np.sqrt(np.mean(tracer_tau_errors**2))),
            "tracerlpm_secondary_mean": float(
                np.mean([row["tracerlpm_secondary"] for row in tracer_selected])
            ),
            "tracerlpm_secondary_bias": float(np.mean(tracer_secondary_errors)),
            "tracerlpm_secondary_rmse": float(
                np.sqrt(np.mean(tracer_secondary_errors**2))
            ),
            "pyage_tracerlpm_tau_rmse": float(np.sqrt(np.mean(pair_tau**2))),
            "pyage_tracerlpm_secondary_rmse": float(
                np.sqrt(np.mean(pair_secondary**2))
            ),
        }
    summary = {
        "campaign_id": config["campaign_id"],
        "noise_relative_sd": 0.01,
        "rows": rows,
        "models": models,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Inversions PyAge–TracerLPM avec bruit relatif de 1 %",
        "",
        "| Modèle | Outil | n | moyenne tau | biais tau | RMSE tau | paramètre 2 | moyenne | biais | RMSE |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for model, stats in models.items():
        lines.append(
            f"| {model} | PyAge | {stats['count']} | {stats['tau_mean']:.6g} | "
            f"{stats['tau_bias']:.6g} | {stats['tau_rmse']:.6g} | {stats['secondary_name']} | "
            f"{stats['secondary_mean']:.6g} | {stats['secondary_bias']:.6g} | {stats['secondary_rmse']:.6g} |"
        )
        lines.append(
            f"| {model} | TracerLPM | {stats['tracerlpm_count']} | {stats['tracerlpm_tau_mean']:.6g} | "
            f"{stats['tracerlpm_tau_bias']:.6g} | {stats['tracerlpm_tau_rmse']:.6g} | {stats['secondary_name']} | "
            f"{stats['tracerlpm_secondary_mean']:.6g} | {stats['tracerlpm_secondary_bias']:.6g} | "
            f"{stats['tracerlpm_secondary_rmse']:.6g} |"
        )
    (OUTPUT / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
