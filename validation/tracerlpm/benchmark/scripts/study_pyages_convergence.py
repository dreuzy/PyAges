# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Study sensitivity to the tracer-grid refinement tolerances."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path

import yaml

from pyages.convolution.settings import DEFAULT_TRACER_GRID_SETTINGS

from .compare_pyages import DEFAULT_INPUT_DIR, DEFAULT_REFERENCE, compare
from .generate_inputs import BENCHMARK_ROOT, DEFAULT_CONFIG

DEFAULT_OUTPUT = BENCHMARK_ROOT / "generated" / "pyages_convergence"


def qualification_by_scale(reports: list[tuple[float, dict]]) -> dict[str, object]:
    """Summarize qualification, requiring the default and tighter grids."""
    scales = []
    for scale, report in reports:
        required = scale <= 1.0
        scales.append(
            {
                "tolerance_scale": scale,
                "required_for_qualification": required,
                "status": report["status"],
                "qualified_case_count": report["qualification"]["qualified_case_count"],
                "failed_case_count": report["qualification"]["failed_case_count"],
            }
        )
    required_scales = [item for item in scales if item["required_for_qualification"]]
    required_pass = bool(required_scales) and all(
        item["status"] == "qualified" for item in required_scales
    )
    return {
        "status": "qualified" if required_pass else "failed_qualification",
        "rule": "all configured tolerance scales <= 1.0 must qualify every case",
        "scales": scales,
    }


def study(
    config_path: Path = DEFAULT_CONFIG, output_dir: Path = DEFAULT_OUTPUT
) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    tolerance_scales = [float(value) for value in config["pyages_grid_tolerance_scales"]]
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
                    qualification_config_path=config_path,
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
        **qualification_by_scale(reports),
        "tolerance_scales": tolerance_scales,
        "families": {
            model: [row for row in rows if row["model"] == model]
            for model in ("PFM", "EMM", "EPM", "DM")
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        "# Sensibilité de la grille PyAges",
        "",
        f"Statut : `{summary['status']}`",
        "",
        "Le verdict exige 270/270 cas conformes aux facteurs 1× et plus stricts.",
        "Les facteurs plus lâches restent informatifs mais ne conditionnent pas le verdict.",
        "",
        "| Facteur de tolérance | Requis | Statut | Cas conformes | Échecs |",
        "|---:|---|---|---:|---:|",
    ]
    for item in summary["scales"]:
        lines.append(
            f"| {item['tolerance_scale']:g} | {item['required_for_qualification']} | "
            f"{item['status']} | {item['qualified_case_count']} | "
            f"{item['failed_case_count']} |"
        )
    lines.extend(
        [
            "",
            "| Facteur de tolérance | Modèle | MAE | RMSE | Max absolu |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['tolerance_scale']:g} | {row['model']} | {row['mae']:.6g} | {row['rmse']:.6g} | {row['maximum_absolute_difference']:.6g} |"
        )
    lines.extend(["", "Les seuils appliqués sont ceux de `campaign.yaml`.", ""])
    (output_dir / "summary.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    """Run the sensitivity study and fail if a required scale is unqualified."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    summary = study(arguments.config, arguments.output)
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "qualified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
