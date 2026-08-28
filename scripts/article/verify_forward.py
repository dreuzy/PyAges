# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Rebuild the forward summary from existing case-level comparison rows."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "validation/tracerlpm/benchmark/generated/pyages_comparison"


def main() -> int:
    source = OUTPUT / "case_results.csv"
    if not source.is_file():
        raise FileNotFoundError(
            "Post-processing refused: missing existing forward rows "
            f"{source.relative_to(ROOT)}"
        )
    with source.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    families = {}
    for model, model_rows in sorted(grouped.items()):
        signed = [float(row["signed_difference"]) for row in model_rows]
        absolute = [abs(value) for value in signed]
        relative = [
            abs(float(row["symmetric_relative_difference"])) for row in model_rows
        ]
        families[model] = {
            "case_count": len(model_rows),
            "bias": sum(signed) / len(signed),
            "mae": sum(absolute) / len(absolute),
            "rmse": math.sqrt(sum(value * value for value in signed) / len(signed)),
            "maximum_absolute_difference": max(absolute),
            "maximum_absolute_symmetric_relative_difference": max(relative),
        }
    payload = {
        "status": "measured_not_yet_qualified",
        "case_count": len(rows),
        "families": families,
        "note": "Rebuilt only from existing case_results.csv; no forward calculation was run.",
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        "# PyAges forward comparison (existing outputs)",
        "",
        "| Model | Cases | Bias | MAE | RMSE | Max absolute | Max symmetric relative |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, item in families.items():
        lines.append(
            f"| {model} | {item['case_count']} | {item['bias']:.6g} | "
            f"{item['mae']:.6g} | {item['rmse']:.6g} | "
            f"{item['maximum_absolute_difference']:.6g} | "
            f"{item['maximum_absolute_symmetric_relative_difference']:.6g} |"
        )
    (OUTPUT / "summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Post-processing complete (no forward calculation): {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
