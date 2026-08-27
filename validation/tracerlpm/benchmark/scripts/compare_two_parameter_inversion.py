# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Compare two-parameter PyAges and TracerLPM inversion results."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .invert_pyages_pilot import RESULT_DIR

ALIASES = {"SF6": "cfc11", "3H": "cfc12", "NO3-N": "cfc113"}


def compare(run_json: Path) -> dict:
    run = json.loads(run_json.read_text(encoding="utf-8-sig"))
    fit = run["fit"]
    model = fit["model"]
    if model not in {"EPM", "DM"}:
        raise ValueError("Un résultat EPM ou DM est requis")
    config = yaml.safe_load(
        (BENCHMARK_ROOT / "configs" / "inversion-campaign.yaml").read_text(
            encoding="utf-8"
        )
    )
    case = next(item for item in config["cases"] if item["model"] == model)
    pyages_path = RESULT_DIR / case["case_id"] / "pyages-result.json"
    pyages = json.loads(pyages_path.read_text(encoding="utf-8"))
    true_tau = float(case["true_parameters"]["tau"])
    pyages_tau = float(pyages["estimated_parameters"]["tau"])
    tracer_tau = float(fit["estimatedAge"])
    if model == "EPM":
        secondary_name, true_secondary = (
            "r",
            float(case["true_parameters"]["eta"]) - 1.0,
        )
        pyages_secondary = float(pyages["estimated_parameters"]["eta"]) - 1.0
    else:
        secondary_name, true_secondary = "DP", float(case["true_parameters"]["DP"])
        pyages_secondary = float(pyages["estimated_parameters"]["DP"])
    tracer_secondary = float(fit["estimatedModelParameter"])
    tau_limit = float(config["acceptance"]["maximum_tau_relative_error"])
    secondary_limit = float(
        config["acceptance"]["maximum_secondary_parameter_relative_error"]
    )
    parameter_rows = [
        {
            "parameter": "tau",
            "true": true_tau,
            "pyages": pyages_tau,
            "tracerlpm": tracer_tau,
            "pyages_relative_error": abs(pyages_tau - true_tau) / true_tau,
            "tracerlpm_relative_error": abs(tracer_tau - true_tau) / true_tau,
        },
        {
            "parameter": secondary_name,
            "true": true_secondary,
            "pyages": pyages_secondary,
            "tracerlpm": tracer_secondary,
            "pyages_relative_error": abs(pyages_secondary - true_secondary)
            / true_secondary,
            "tracerlpm_relative_error": abs(tracer_secondary - true_secondary)
            / true_secondary,
        },
    ]
    best_attempt = min(fit["attempts"], key=lambda item: item["objective"])
    concentrations = []
    observed_by_alias = fit["observations"]
    for alias, calculated in best_attempt["calculatedConcentrations"].items():
        observed = float(observed_by_alias[alias])
        concentrations.append(
            {
                "tracer": ALIASES[alias],
                "alias": alias,
                "observed": observed,
                "tracerlpm_calculated": float(calculated),
                "tracerlpm_relative_error": abs(float(calculated) - observed)
                / observed,
            }
        )
    output = RESULT_DIR / case["case_id"]
    raw = BENCHMARK_ROOT / "tracerlpm_exports_raw" / run_json.name
    shutil.copy2(run_json, raw)
    summary = {
        "case_id": case["case_id"],
        "model": model,
        "parameter_comparison": parameter_rows,
        "concentration_comparison": concentrations,
        "pyages_pass": parameter_rows[0]["pyages_relative_error"] <= tau_limit
        and parameter_rows[1]["pyages_relative_error"] <= secondary_limit,
        "tracerlpm_pass": parameter_rows[0]["tracerlpm_relative_error"] <= tau_limit
        and parameter_rows[1]["tracerlpm_relative_error"] <= secondary_limit,
        "tau_relative_error_limit": tau_limit,
        "secondary_relative_error_limit": secondary_limit,
        "objective_formula": fit["objectiveFormula"],
        "tracer_selection": fit["tracerSelectionLabel"],
        "raw_report": raw.relative_to(BENCHMARK_ROOT).as_posix(),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Inversion {model} sans bruit — trois CFC",
        "",
        "| Paramètre | Vrai | PyAges | TracerLPM | Erreur rel. PyAges | Erreur rel. TracerLPM |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in parameter_rows:
        lines.append(
            f"| {row['parameter']} | {row['true']:.9g} | {row['pyages']:.9g} | {row['tracerlpm']:.9g} | {row['pyages_relative_error']:.3%} | {row['tracerlpm_relative_error']:.3%} |"
        )
    lines += [
        "",
        f"Verdicts : PyAges `{'pass' if summary['pyages_pass'] else 'investigate'}` ; TracerLPM `{'pass' if summary['tracerlpm_pass'] else 'investigate'}`.",
        "",
    ]
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-json", type=Path, required=True)
    print(json.dumps(compare(parser.parse_args().run_json), indent=2))
