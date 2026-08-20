"""Compare paired 3-CFC and 3-CFC+SF6 Monte-Carlo inversion campaigns."""

from __future__ import annotations

import json

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import expanded_cases
from .invert_pyage_pilot import RESULT_DIR

CONFIGS = {
    "three_cfcs": BENCHMARK_ROOT / "configs" / "inversion-monte-carlo-01.yaml",
    "three_cfcs_plus_sf6": BENCHMARK_ROOT
    / "configs"
    / "inversion-monte-carlo-01-sf6.yaml",
}
OUTPUT = BENCHMARK_ROOT / "generated" / "sf6-information-gain"


def _load(path, prefix: str) -> dict[str, list[dict]]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = {"EPM": [], "DM": []}
    for case in expanded_cases(config):
        result = json.loads(
            (RESULT_DIR / case["case_id"] / "pyage-result.json").read_text(
                encoding="utf-8"
            )
        )
        secondary_key = "eta" if case["model"] == "EPM" else "DP"
        secondary = float(result["estimated_parameters"][secondary_key])
        if case["model"] == "EPM":
            secondary -= 1.0
        rows[case["model"]].append(
            {
                "seed": int(case["noise"]["seed"]),
                "tau": float(result["estimated_parameters"]["tau"]),
                "secondary": secondary,
                "source": prefix,
            }
        )
    for values in rows.values():
        values.sort(key=lambda row: row["seed"])
    return rows


def _metrics(rows: list[dict], secondary_truth: float) -> dict:
    tau = np.asarray([row["tau"] for row in rows])
    secondary = np.asarray([row["secondary"] for row in rows])
    return {
        "tau_sd": float(np.std(tau, ddof=1)),
        "tau_rmse": float(np.sqrt(np.mean((tau - 20.0) ** 2))),
        "secondary_sd": float(np.std(secondary, ddof=1)),
        "secondary_rmse": float(np.sqrt(np.mean((secondary - secondary_truth) ** 2))),
        "tau_secondary_correlation": float(np.corrcoef(tau, secondary)[0, 1]),
    }


def compare() -> dict:
    campaigns = {name: _load(path, name) for name, path in CONFIGS.items()}
    models = {}
    for model, secondary_name, truth in (("EPM", "r", 2.0), ("DM", "DP", 0.2)):
        before = _metrics(campaigns["three_cfcs"][model], truth)
        after = _metrics(campaigns["three_cfcs_plus_sf6"][model], truth)
        reductions = {
            key: 1.0 - after[key] / before[key]
            for key in ("tau_sd", "tau_rmse", "secondary_sd", "secondary_rmse")
        }
        models[model] = {
            "secondary_name": secondary_name,
            "three_cfcs": before,
            "three_cfcs_plus_sf6": after,
            "relative_reductions": reductions,
        }
    summary = {
        "paired_seeds": list(range(201, 231)),
        "noise_relative_sd": 0.01,
        "models": models,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Gain d'information du SF6 — 30 réalisations appariées",
        "",
        "| Modèle | Mesure | 3 CFC | 3 CFC + SF6 | Réduction |",
        "|---|---|---:|---:|---:|",
    ]
    labels = {
        "tau_sd": "écart type tau",
        "tau_rmse": "RMSE tau",
        "secondary_sd": "écart type paramètre 2",
        "secondary_rmse": "RMSE paramètre 2",
    }
    for model, data in models.items():
        for key, label in labels.items():
            lines.append(
                f"| {model} | {label} | {data['three_cfcs'][key]:.6g} | "
                f"{data['three_cfcs_plus_sf6'][key]:.6g} | {data['relative_reductions'][key]:.1%} |"
            )
        lines.append(
            f"| {model} | corrélation tau–{data['secondary_name']} | "
            f"{data['three_cfcs']['tau_secondary_correlation']:.6g} | "
            f"{data['three_cfcs_plus_sf6']['tau_secondary_correlation']:.6g} | — |"
        )
    (OUTPUT / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
