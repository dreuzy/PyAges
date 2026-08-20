"""Compare the PyAge production convolution path with independent references."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from pyage.convolution.convolution import Convolution
from pyage.convolution.settings import (
    DEFAULT_TRACER_GRID_SETTINGS,
    TracerGridSettings,
)
from pyage.lpm.lpm_build import lpm_build
from pyage.tracer.tracer_protocol import SyntheticTracer

from .generate_inputs import BENCHMARK_ROOT
from .mappings import dm_to_inverse_gaussian, epm_to_shifted_exponential

DEFAULT_REFERENCE = BENCHMARK_ROOT / "references" / "forward_reference.csv"
DEFAULT_INPUT_DIR = BENCHMARK_ROOT / "inputs" / "synthetic"
DEFAULT_OUTPUT_DIR = BENCHMARK_ROOT / "generated" / "pyage_comparison"
MODEL_NAMES = {"PFM": "dirac", "EMM": "exp", "EPM": "exp_shifted", "DM": "ig"}


def parse_parameters(text: str) -> dict[str, float]:
    return {
        item.split("=", 1)[0]: float(item.split("=", 1)[1]) for item in text.split(";")
    }


def pyage_parameters(model: str, parameters: dict[str, float]) -> dict[str, float]:
    if model in {"PFM", "EMM"}:
        return {"mu": parameters["tau"]}
    if model == "EPM":
        mapped = epm_to_shifted_exponential(parameters["tau"], parameters["eta"])
        return {"mu": mapped.mu, "shift": mapped.shift}
    if model == "DM":
        mapped = dm_to_inverse_gaussian(parameters["tau"], parameters["DP"])
        return {"mu": mapped.mu, "sigma": mapped.sigma}
    raise ValueError(f"Unknown model {model}")


def load_tracer(path: Path) -> SyntheticTracer:
    data = np.genfromtxt(path, delimiter=",", names=True)
    years = np.asarray(data["date"], dtype=float)
    values = np.asarray(data["concentration"], dtype=float)

    def concentration(date, _time):
        return np.interp(date, years, values, left=0.0, right=values[-1])

    return SyntheticTracer(
        name=path.stem,
        unit="au",
        datemin=float(years[0]),
        datemax=float(years[-1]),
        concentration_fn=concentration,
    )


def symmetric_relative_difference(
    value: float, reference: float, floor: float = 1e-12
) -> float:
    return 2 * (value - reference) / max(abs(value) + abs(reference), floor)


def compare(
    reference_path: Path = DEFAULT_REFERENCE,
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    grid_settings: TracerGridSettings | None = None,
) -> dict:
    with reference_path.open(encoding="utf-8", newline="") as stream:
        references = list(csv.DictReader(stream))
    tracers = {path.stem: load_tracer(path) for path in sorted(input_dir.glob("*.csv"))}
    lpms = {model: lpm_build(name) for model, name in MODEL_NAMES.items()}
    effective_grid_settings = grid_settings or DEFAULT_TRACER_GRID_SETTINGS
    rows = []
    for reference in references:
        model = reference["model"]
        parameters = parse_parameters(reference["parameters"])
        lpm = lpms[model]
        effective_parameters = pyage_parameters(model, parameters)
        lpm.p.update(effective_parameters)
        convolution = Convolution(
            tracers[reference["input"]],
            date=float(reference["observation_year"]),
            grid_settings=effective_grid_settings,
        )
        value = float(convolution.convolve(lpm))
        expected = float(reference["concentration"])
        signed = value - expected
        rows.append(
            {
                **reference,
                "pyage_model": MODEL_NAMES[model],
                "pyage_parameters": ";".join(
                    f"{key}={val:.12g}" for key, val in effective_parameters.items()
                ),
                "pyage_concentration": value,
                "signed_difference": signed,
                "absolute_difference": abs(signed),
                "symmetric_relative_difference": symmetric_relative_difference(
                    value, expected
                ),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "case_results.csv"
    fieldnames = list(rows[0])
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: f"{value:.12g}" if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)
    families = {}
    for model, model_rows in grouped.items():
        differences = np.asarray([row["signed_difference"] for row in model_rows])
        absolute = np.abs(differences)
        relative = np.abs([row["symmetric_relative_difference"] for row in model_rows])
        families[model] = {
            "case_count": len(model_rows),
            "bias": float(np.mean(differences)),
            "mae": float(np.mean(absolute)),
            "rmse": float(np.sqrt(np.mean(differences**2))),
            "maximum_absolute_difference": float(np.max(absolute)),
            "maximum_absolute_symmetric_relative_difference": float(np.max(relative)),
        }
    report = {
        "status": "measured_not_yet_qualified",
        "case_count": len(rows),
        "tracer_grid_settings": asdict(effective_grid_settings),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes())
        .hexdigest()
        .upper(),
        "results_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest().upper(),
        "families": families,
        "note": "No pass/fail threshold is applied before the convergence study.",
    }
    json_path = output_dir / "summary.json"
    json_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    markdown = [
        "# Comparaison PyAge–référence indépendante",
        "",
        f"Statut : `{report['status']}`",
        "",
        "| Modèle | Cas | Biais | MAE | RMSE | Max absolu | Max relatif symétrique |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model in MODEL_NAMES:
        item = families[model]
        markdown.append(
            f"| {model} | {item['case_count']} | {item['bias']:.6g} | {item['mae']:.6g} | {item['rmse']:.6g} | {item['maximum_absolute_difference']:.6g} | {item['maximum_absolute_symmetric_relative_difference']:.6g} |"
        )
    markdown.extend(
        ["", "Aucun verdict pass/fail n’est appliqué avant l’étude de convergence.", ""]
    )
    (output_dir / "summary.md").write_text(
        "\n".join(markdown), encoding="utf-8", newline="\n"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
