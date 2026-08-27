# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Build the retained PyAges/TracerLPM EMM inversion pilot report."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .invert_pyages_pilot import RESULT_DIR


def compare(run_json: Path) -> dict:
    run = json.loads(run_json.read_text(encoding="utf-8-sig"))
    fit = run.get("fit")
    if not fit or fit["model"] != "EMM":
        raise ValueError("Un rapport d'inversion EMM TracerLPM est requis")
    pyages_path = RESULT_DIR / "inversion-emm-tau20-no-noise" / "pyages-result.json"
    pyages = json.loads(pyages_path.read_text(encoding="utf-8"))
    config = yaml.safe_load(
        (BENCHMARK_ROOT / "configs" / "inversion-campaign.yaml").read_text(
            encoding="utf-8"
        )
    )
    true_tau = float(pyages["true_tau"])
    threshold = float(config["acceptance"]["maximum_tau_absolute_error_years"])
    output = RESULT_DIR / "inversion-emm-tau20-no-noise"
    output.mkdir(parents=True, exist_ok=True)
    raw = BENCHMARK_ROOT / "tracerlpm_exports_raw" / run_json.name
    shutil.copy2(run_json, raw)
    summary = {
        "case_id": "inversion-emm-tau20-no-noise",
        "true_tau": true_tau,
        "pyages_estimated_tau": float(pyages["estimated_tau"]),
        "pyages_tau_absolute_error": float(pyages["tau_absolute_error"]),
        "tracerlpm_estimated_tau": float(fit["estimatedAge"]),
        "tracerlpm_tau_absolute_error": abs(float(fit["estimatedAge"]) - true_tau),
        "maximum_tau_absolute_error_years": threshold,
        "pyages_pass": float(pyages["tau_absolute_error"]) <= threshold,
        "tracerlpm_pass": abs(float(fit["estimatedAge"]) - true_tau) <= threshold,
        "parameter_comparison": [
            {
                "parameter": "tau",
                "unit": "year",
                "true_value": true_tau,
                "pyages_value": float(pyages["estimated_tau"]),
                "tracerlpm_value": float(fit["estimatedAge"]),
            }
        ],
        "tracerlpm_attempts": fit["attempts"],
        "scope_note": (
            "Both tools use CFC-11, CFC-12 and CFC-113. TracerLPM aliases them "
            "to SF6, decay-neutralized 3H and NO3-N workbook channels."
        ),
        "tracerlpm_raw_report": raw.relative_to(BENCHMARK_ROOT).as_posix(),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    markdown = f"""# Pilote d’inversion EMM sans bruit

| Outil | Tau vrai | Tau estimé | Erreur absolue | Seuil | Verdict |
|---|---:|---:|---:|---:|---|
| PyAges | {true_tau:g} | {summary["pyages_estimated_tau"]:.9g} | {summary["pyages_tau_absolute_error"]:.6g} | {threshold:g} | {"pass" if summary["pyages_pass"] else "investigate"} |
| TracerLPM | {true_tau:g} | {summary["tracerlpm_estimated_tau"]:.9g} | {summary["tracerlpm_tau_absolute_error"]:.6g} | {threshold:g} | {"pass" if summary["tracerlpm_pass"] else "investigate"} |

Les deux outils utilisent CFC-11, CFC-12 et CFC-113. TracerLPM les reçoit par
des alias explicites dans les canaux SF6, 3H et NO3-N du classeur Example 1 ;
le taux de décroissance du canal 3H est imposé à zéro. Aucune conversion
physico-chimique n’est appliquée.

Les trois initialisations Solver sont conservées dans `summary.json`; le départ
à 5 ans atteint une mauvaise borne, ce qui confirme la nécessité du multi-départ.
"""
    (output / "summary.md").write_text(markdown, encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-json", required=True, type=Path)
    print(json.dumps(compare(parser.parse_args().run_json), indent=2))
