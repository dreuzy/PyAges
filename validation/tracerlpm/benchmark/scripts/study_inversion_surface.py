"""Compute independent EPM or DM objective surfaces for identifiability."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import yaml

from .generate_inversion_pilot import DEFAULT_CONFIG, OUTPUT_DIR, REPO_ROOT, _chronicle
from .invert_pyage_pilot import RESULT_DIR
from .reference import forward


def study(
    config_path: Path = DEFAULT_CONFIG,
    observation_dir: Path = OUTPUT_DIR,
    output_dir: Path | None = None,
    model: str = "EPM",
) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = model.upper()
    if model not in {"EPM", "DM"}:
        raise ValueError("La surface accepte EPM ou DM")
    case = next(item for item in config["cases"] if item["model"] == model)
    output_dir = output_dir or RESULT_DIR / case["case_id"]
    with (observation_dir / f"{case['case_id']}.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        observations = list(csv.DictReader(stream))
    histories = {}
    maxima = {}
    for tracer in config["tracers"]:
        dates, values = _chronicle(REPO_ROOT / tracer["recharge"])
        histories[tracer["name"]] = (dates, values)
        maxima[tracer["name"]] = float(np.max(values))
    relative = float(config["objective"]["relative_standard_deviation"])
    floor_fraction = float(
        config["objective"]["absolute_floor_fraction_of_tracer_maximum"]
    )
    date = float(config["observation_year"])
    tau_values = np.unique(
        np.append(np.linspace(5.0, 60.0, 31), case["true_parameters"]["tau"])
    )
    secondary_name = "eta" if model == "EPM" else "DP"
    secondary_values = (
        np.unique(
            np.append(np.linspace(1.05, 10.0, 31), case["true_parameters"]["eta"])
        )
        if model == "EPM"
        else np.unique(
            np.append(np.geomspace(0.005, 3.0, 31), case["true_parameters"]["DP"])
        )
    )
    rows = []
    for tau in tau_values:
        for secondary in secondary_values:
            objective = 0.0
            for observation in observations:
                name = observation["tracer"]
                dates, values = histories[name]
                predicted = forward(
                    model,
                    {"tau": tau, secondary_name: secondary},
                    date,
                    lambda year, d=dates, v=values: np.interp(
                        year, d, v, left=0.0, right=v[-1]
                    ),
                    date - dates[0],
                    date - dates,
                )[0]
                observed = float(observation["observed_concentration"])
                scale = max(relative * observed, floor_fraction * maxima[name])
                objective += ((predicted - observed) / scale) ** 2
            row = {
                "tau": float(tau),
                secondary_name: float(secondary),
                "objective_chi_square": float(objective),
            }
            if model == "EPM":
                row["tracerlpm_r"] = float(secondary - 1)
            rows.append(row)
    best = min(rows, key=lambda row: row["objective_chi_square"])
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "objective-surface.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "case_id": case["case_id"],
        "model": model,
        "grid_shape": [len(tau_values), len(secondary_values)],
        "true_parameters": case["true_parameters"],
        "grid_best": best,
        "note": "Coarse independent surface; optimizer results remain the precision estimate.",
    }
    (output_dir / "surface-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["EPM", "DM"], default="EPM")
    print(json.dumps(study(model=parser.parse_args().model), indent=2))
