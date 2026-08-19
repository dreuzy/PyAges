"""Generate slow forward reference values for every configured synthetic case."""

from __future__ import annotations

import csv
import hashlib
import itertools
from pathlib import Path

import numpy as np
import scipy
import yaml

from .generate_inputs import BENCHMARK_ROOT, DEFAULT_CONFIG, build_series
from .reference import forward

DEFAULT_OUTPUT = BENCHMARK_ROOT / "references" / "forward_reference.csv"
DEFAULT_MANIFEST = BENCHMARK_ROOT / "references" / "manifest.yaml"


def _parameter_sets(model: str, grid: dict) -> list[dict]:
    names = list(grid)
    return [
        dict(zip(names, values))
        for values in itertools.product(*(grid[name] for name in names))
    ]


def generate(
    config_path: Path = DEFAULT_CONFIG,
    output_path: Path = DEFAULT_OUTPUT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict:
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    years, inputs = build_series(config)
    before = float(config["outside_domain"]["before"])
    rows = []
    for input_name, values in inputs.items():

        def input_function(year: float, values=values) -> float:
            return np.interp(year, years, values, left=before, right=values[-1])

        for model, parameter_grid in config["models"].items():
            for parameters in _parameter_sets(model, parameter_grid):
                for observation_year in config["observation_years"]:
                    value, mass = forward(
                        model,
                        parameters,
                        float(observation_year),
                        input_function,
                        float(observation_year) - float(years[0]),
                        float(observation_year) - years,
                    )
                    parameter_text = ";".join(
                        f"{key}={float(val):.12g}" for key, val in parameters.items()
                    )
                    rows.append(
                        (
                            input_name,
                            model,
                            parameter_text,
                            float(observation_year),
                            value,
                            mass,
                        )
                    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "input",
                "model",
                "parameters",
                "observation_year",
                "concentration",
                "covered_mass",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row[0],
                    row[1],
                    row[2],
                    f"{row[3]:.12f}",
                    f"{row[4]:.12f}",
                    f"{row[5]:.12f}",
                ]
            )
    manifest = {
        "campaign_id": config["campaign_id"],
        "kind": "independent_forward_reference",
        "row_count": len(rows),
        "campaign_config_sha256": hashlib.sha256(config_bytes).hexdigest().upper(),
        "forward_reference_sha256": hashlib.sha256(output_path.read_bytes())
        .hexdigest()
        .upper(),
        "environment": {"numpy": np.__version__, "scipy": scipy.__version__},
        "numerics": {
            "method": "composite 8-point Gauss-Legendre split at every monthly interpolation knot",
            "points_per_interval": 8,
        },
    }
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8", newline="\n"
    )
    return manifest


if __name__ == "__main__":
    print(yaml.safe_dump(generate(), sort_keys=False), end="")
