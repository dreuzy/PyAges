# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Compare the PyAges production convolution path with independent references."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import yaml

from pyages.convolution.convolution import Convolution
from pyages.convolution.settings import (
    DEFAULT_TRACER_GRID_SETTINGS,
    TracerGridSettings,
)
from pyages.lpm import build_lpm
from pyages.tracer.tracer_protocol import SyntheticTracer

from .generate_inputs import BENCHMARK_ROOT, DEFAULT_CONFIG
from .mappings import dm_to_inverse_gaussian, epm_to_shifted_exponential

DEFAULT_REFERENCE = BENCHMARK_ROOT / "references" / "forward_reference.csv"
DEFAULT_INPUT_DIR = BENCHMARK_ROOT / "inputs" / "synthetic"
DEFAULT_OUTPUT_DIR = BENCHMARK_ROOT / "generated" / "pyages_comparison"
MODEL_NAMES = {"PFM": "dirac", "EMM": "exp", "EPM": "exp_shifted", "DM": "ig"}


@dataclass(frozen=True)
class ForwardQualificationThresholds:
    """Numerical acceptance thresholds for independent forward comparisons."""

    contract_version: int = 1
    significant_concentration_fraction_of_input_scale: float = 1e-3
    maximum_significant_symmetric_relative_difference: float = 5e-4
    maximum_near_zero_absolute_difference_fraction_of_input_scale: float = 2e-5
    physical_bound_tolerance_fraction_of_input_scale: float = 1e-12
    require_all_cases: bool = True

    def __post_init__(self) -> None:
        positive = (
            self.significant_concentration_fraction_of_input_scale,
            self.maximum_significant_symmetric_relative_difference,
            self.maximum_near_zero_absolute_difference_fraction_of_input_scale,
            self.physical_bound_tolerance_fraction_of_input_scale,
        )
        if self.contract_version < 1 or any(
            not np.isfinite(value) or value <= 0 for value in positive
        ):
            raise ValueError("Forward qualification thresholds must be positive")
        if not self.require_all_cases:
            raise ValueError("Forward qualification requires every case to pass")


def load_qualification_thresholds(
    config_path: Path = DEFAULT_CONFIG,
) -> ForwardQualificationThresholds:
    """Load the versioned forward-qualification contract."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    values = config["forward_qualification"]
    require_all_cases = values["require_all_cases"]
    if not isinstance(require_all_cases, bool):
        raise ValueError("require_all_cases must be a YAML boolean")
    return ForwardQualificationThresholds(
        contract_version=int(values["contract_version"]),
        significant_concentration_fraction_of_input_scale=float(
            values["significant_concentration_fraction_of_input_scale"]
        ),
        maximum_significant_symmetric_relative_difference=float(
            values["maximum_significant_symmetric_relative_difference"]
        ),
        maximum_near_zero_absolute_difference_fraction_of_input_scale=float(
            values["maximum_near_zero_absolute_difference_fraction_of_input_scale"]
        ),
        physical_bound_tolerance_fraction_of_input_scale=float(
            values["physical_bound_tolerance_fraction_of_input_scale"]
        ),
        require_all_cases=require_all_cases,
    )


def parse_parameters(text: str) -> dict[str, float]:
    return {
        item.split("=", 1)[0]: float(item.split("=", 1)[1]) for item in text.split(";")
    }


def pyages_parameters(model: str, parameters: dict[str, float]) -> dict[str, float]:
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


def input_concentration_scale(path: Path) -> float:
    """Return the finite positive amplitude used to normalize qualification."""
    data = np.genfromtxt(path, delimiter=",", names=True)
    values = np.asarray(data["concentration"], dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError(f"Input history has no finite concentration scale: {path}")
    tolerance = np.finfo(float).eps * max(1.0, float(np.max(np.abs(values))))
    if float(np.min(values)) < -tolerance:
        raise ValueError(f"Forward qualification requires non-negative input: {path}")
    scale = float(np.max(np.abs(values)))
    if scale <= 0:
        raise ValueError(f"Input history has a zero concentration scale: {path}")
    return scale


def symmetric_relative_difference(
    value: float, reference: float, floor: float = 1e-12
) -> float:
    return 2 * (value - reference) / max(abs(value) + abs(reference), floor)


def qualify_forward_case(
    value: float,
    reference: float,
    input_scale: float,
    thresholds: ForwardQualificationThresholds,
) -> dict[str, object]:
    """Apply the two-regime forward-qualification contract to one case."""
    if not np.isfinite(input_scale) or input_scale <= 0:
        raise ValueError("input_scale must be finite and positive")
    finite = bool(np.isfinite(value) and np.isfinite(reference))
    significance_threshold = (
        thresholds.significant_concentration_fraction_of_input_scale * input_scale
    )
    significant = finite and max(abs(value), abs(reference)) >= significance_threshold
    absolute_difference = abs(value - reference) if finite else None
    absolute_symmetric_relative_difference = (
        abs(symmetric_relative_difference(value, reference)) if finite else None
    )
    if not finite:
        regime = "invalid"
        metric = None
        limit = None
    elif significant:
        regime = "significant"
        metric = absolute_symmetric_relative_difference
        limit = thresholds.maximum_significant_symmetric_relative_difference
    else:
        regime = "near_zero"
        metric = absolute_difference
        limit = (
            thresholds.maximum_near_zero_absolute_difference_fraction_of_input_scale
            * input_scale
        )
    physical_tolerance = (
        thresholds.physical_bound_tolerance_fraction_of_input_scale * input_scale
    )
    within_bounds = finite and all(
        -physical_tolerance <= candidate <= input_scale + physical_tolerance
        for candidate in (value, reference)
    )
    qualified = (
        finite
        and within_bounds
        and metric is not None
        and limit is not None
        and metric <= limit
    )
    return {
        "input_scale": input_scale,
        "qualification_regime": regime,
        "qualification_metric": metric,
        "qualification_threshold": limit,
        "qualification_budget_fraction": (
            metric / limit if metric is not None and limit is not None else None
        ),
        "finite": finite,
        "within_physical_bounds": within_bounds,
        "qualified": qualified,
    }


def _qualification_summary(
    rows: list[dict[str, object]],
    thresholds: ForwardQualificationThresholds,
) -> dict[str, object]:
    significant = [row for row in rows if row["qualification_regime"] == "significant"]
    near_zero = [row for row in rows if row["qualification_regime"] == "near_zero"]
    invalid = [row for row in rows if row["qualification_regime"] == "invalid"]
    qualified_count = sum(bool(row["qualified"]) for row in rows)

    def maximum(items: list[dict[str, object]], field: str) -> float:
        values = [float(item[field]) for item in items if item[field] is not None]
        return max(values, default=0.0)

    return {
        "contract_version": thresholds.contract_version,
        "thresholds": asdict(thresholds),
        "input_scale_definition": "maximum absolute input-history concentration",
        "significant_case_count": len(significant),
        "near_zero_case_count": len(near_zero),
        "invalid_case_count": len(invalid),
        "qualified_case_count": qualified_count,
        "failed_case_count": len(rows) - qualified_count,
        "all_cases_qualified": bool(rows) and qualified_count == len(rows),
        "maximum_significant_absolute_symmetric_relative_difference": maximum(
            significant, "qualification_metric"
        ),
        "maximum_near_zero_absolute_difference": maximum(
            near_zero, "qualification_metric"
        ),
        "maximum_qualification_budget_fraction": maximum(
            rows, "qualification_budget_fraction"
        ),
    }


def compare(
    reference_path: Path = DEFAULT_REFERENCE,
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    grid_settings: TracerGridSettings | None = None,
    qualification_config_path: Path = DEFAULT_CONFIG,
    qualification_thresholds: ForwardQualificationThresholds | None = None,
) -> dict:
    with reference_path.open(encoding="utf-8", newline="") as stream:
        references = list(csv.DictReader(stream))
    input_paths = sorted(input_dir.glob("*.csv"))
    tracers = {path.stem: load_tracer(path) for path in input_paths}
    input_scales = {path.stem: input_concentration_scale(path) for path in input_paths}
    lpms = {model: build_lpm(name) for model, name in MODEL_NAMES.items()}
    effective_grid_settings = grid_settings or DEFAULT_TRACER_GRID_SETTINGS
    effective_thresholds = qualification_thresholds or load_qualification_thresholds(
        qualification_config_path
    )
    rows = []
    for reference in references:
        model = reference["model"]
        parameters = parse_parameters(reference["parameters"])
        lpm = lpms[model]
        effective_parameters = pyages_parameters(model, parameters)
        lpm.p.update(effective_parameters)
        convolution = Convolution(
            tracers[reference["input"]],
            date=float(reference["observation_year"]),
            grid_settings=effective_grid_settings,
        )
        value = float(convolution.convolve(lpm))
        expected = float(reference["concentration"])
        signed = value - expected
        qualification = qualify_forward_case(
            value,
            expected,
            input_scales[reference["input"]],
            effective_thresholds,
        )
        rows.append(
            {
                **reference,
                "pyages_model": MODEL_NAMES[model],
                "pyages_parameters": ";".join(
                    f"{key}={val:.12g}" for key, val in effective_parameters.items()
                ),
                "pyages_concentration": value,
                "signed_difference": signed,
                "absolute_difference": abs(signed),
                "symmetric_relative_difference": symmetric_relative_difference(
                    value, expected
                ),
                **qualification,
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
            "qualified_case_count": sum(bool(row["qualified"]) for row in model_rows),
            "failed_case_count": sum(not bool(row["qualified"]) for row in model_rows),
        }
    qualification = _qualification_summary(rows, effective_thresholds)
    status = (
        "qualified" if qualification["all_cases_qualified"] else "failed_qualification"
    )
    report = {
        "status": status,
        "case_count": len(rows),
        "tracer_grid_settings": asdict(effective_grid_settings),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes())
        .hexdigest()
        .upper(),
        "results_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest().upper(),
        "qualification_config_sha256": (
            hashlib.sha256(qualification_config_path.read_bytes()).hexdigest().upper()
            if qualification_thresholds is None
            else None
        ),
        "qualification": qualification,
        "families": families,
        "note": (
            "Every case must satisfy the versioned two-regime numerical "
            "qualification contract."
        ),
    }
    json_path = output_dir / "summary.json"
    json_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    markdown = [
        "# Comparaison PyAges–référence indépendante",
        "",
        f"Statut : `{report['status']}`",
        "",
        "## Contrat de qualification",
        "",
        "| Régime | Frontière | Métrique | Seuil |",
        "|---|---:|---|---:|",
        (
            "| concentration significative | "
            f"≥ {effective_thresholds.significant_concentration_fraction_of_input_scale:g} × amplitude | "
            "écart relatif symétrique absolu | "
            f"{effective_thresholds.maximum_significant_symmetric_relative_difference:g} |"
        ),
        (
            "| proche de zéro | sous la frontière | écart absolu | "
            f"{effective_thresholds.maximum_near_zero_absolute_difference_fraction_of_input_scale:g} × amplitude |"
        ),
        "",
        (
            f"Verdict : {qualification['qualified_case_count']}/{len(rows)} cas "
            f"conformes ; budget maximal utilisé : "
            f"{qualification['maximum_qualification_budget_fraction']:.3f}."
        ),
        "",
        "| Modèle | Cas | Biais | MAE | RMSE | Max absolu | Max relatif symétrique |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model in MODEL_NAMES:
        item = families[model]
        markdown.append(
            f"| {model} | {item['case_count']} | {item['bias']:.6g} | {item['mae']:.6g} | {item['rmse']:.6g} | {item['maximum_absolute_difference']:.6g} | {item['maximum_absolute_symmetric_relative_difference']:.6g} |"
        )
    markdown.extend(["", "Le verdict global exige la conformité de chaque cas.", ""])
    (output_dir / "summary.md").write_text(
        "\n".join(markdown), encoding="utf-8", newline="\n"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    """Run the comparison and fail the process when qualification fails."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    arguments = parser.parse_args(argv)
    report = compare(
        arguments.reference,
        arguments.input_dir,
        arguments.output,
        qualification_config_path=arguments.config,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "qualified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
