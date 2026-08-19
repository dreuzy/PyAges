"""Study sensitivity to the tracer-grid refinement tolerances."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import yaml

from pyage.convolution.settings import DEFAULT_TRACER_GRID_SETTINGS

from .compare_pyage import DEFAULT_INPUT_DIR, DEFAULT_REFERENCE, compare
from .generate_inputs import BENCHMARK_ROOT, DEFAULT_CONFIG


DEFAULT_OUTPUT = BENCHMARK_ROOT / "generated" / "pyage_convergence"


def study(config_path: Path = DEFAULT_CONFIG, output_dir: Path = DEFAULT_OUTPUT) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    tolerance_scales = [
        float(value) for value in config["pyage_grid_tolerance_scales"]
    ]
    reports = []
    for scale in tolerance_scales:
        settings = replace(
            DEFAULT_TRACER_GRID_SETTINGS,
            absolute_tolerance_factor=(
                DEFAULT_TRACER_GRID_SETTINGS.absolute_tolerance_factor * scale
            ),
            relative_tolerance=(
                DEFAULT_TRACER_GRID_SETTINGS.relative_tolerance * scale
            ),
        )
        label = f"tolerance_scale_{scale:g}".replace(".", "p")
        reports.append(
            (
                scale,
                compare(
                    DEFAULT_REFERENCE,
                    DEFAULT_INPUT_DIR,
                    output_dir / label,
                    grid_settings=settings,
                ),
            )
        )
    rows = []
    for scale, report in reports:
        for model, metrics in report["families"].items():
            rows.append({"tolerance_scale": scale, "model": model, **metrics})
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "convergence.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "status": "convergence_measured_not_yet_qualified",
        "tolerance_scales": tolerance_scales,
        "families": {
            model: [row for row in rows if row["model"] == model]
            for model in ("PFM", "EMM", "EPM", "DM")
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Sensibilité de la grille PyAge", "", "| Facteur de tolérance | Modèle | MAE | RMSE | Max absolu |", "|---:|---|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['tolerance_scale']:g} | {row['model']} | {row['mae']:.6g} | {row['rmse']:.6g} | {row['maximum_absolute_difference']:.6g} |")
    lines.extend(["", "Ces mesures ne constituent pas encore des tolérances d’acceptation.", ""])
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(study(), indent=2))
