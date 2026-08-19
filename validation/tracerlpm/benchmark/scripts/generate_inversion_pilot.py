"""Generate inversion observations with independent quadrature and declared noise."""

from __future__ import annotations

import csv
import hashlib
import json
import copy
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .generate_inputs import BENCHMARK_ROOT
from .reference import forward


REPO_ROOT = BENCHMARK_ROOT.parents[2]
DEFAULT_CONFIG = BENCHMARK_ROOT / "configs" / "inversion-campaign.yaml"
OUTPUT_DIR = BENCHMARK_ROOT / "observations"


def expanded_cases(config: dict) -> list[dict]:
    """Return explicit cases, expanding compact templates and study matrices."""
    cases = list(config.get("cases", []))
    for template in config.get("case_templates", []):
        for seed in template["seeds"]:
            case = copy.deepcopy(template)
            case.pop("seeds")
            case["case_id"] = template["case_id_pattern"].format(seed=seed)
            case.pop("case_id_pattern")
            case["noise"]["seed"] = int(seed)
            cases.append(case)
    for matrix in config.get("case_matrices", []):
        secondary = matrix["secondary_parameter"]
        for tau, shape, noise, seed in itertools.product(
            matrix["tau_values"], secondary["values"],
            matrix["noise_relative_standard_deviations"], matrix["seeds"],
        ):
            tau = float(tau)
            shape = float(shape)
            noise = float(noise)
            seed = int(seed)
            context = {
                "tau_tag": _number_tag(tau),
                "shape_tag": _number_tag(shape),
                "noise_percent": int(round(100.0 * noise)),
                "seed": seed,
            }
            model_parameter = secondary["model_parameter"]
            model_value = shape + float(secondary.get("model_offset", 0.0))
            cases.append({
                "case_id": matrix["case_id_pattern"].format(**context),
                "model": matrix["model"],
                "true_parameters": {"tau": tau, model_parameter: model_value},
                "bounds": copy.deepcopy(matrix["bounds"]),
                "initial_values": copy.deepcopy(matrix["initial_values"]),
                "noise": {
                    "kind": "gaussian_relative",
                    "relative_standard_deviation": noise,
                    "seed": seed,
                },
            })
    identifiers = [case["case_id"] for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Les identifiants de cas doivent être uniques après expansion")
    return cases


def _number_tag(value: float) -> str:
    """Return a stable, filesystem-safe decimal tag (0.05 -> 0p05)."""
    return format(value, ".12g").replace("-", "m").replace(".", "p")


def _chronicle(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = pd.read_csv(path, comment="#")
    if list(data.columns) != ["date", "concentration"]:
        # CFC-12 central is headerless. Re-read it explicitly without modifying
        # the source; the normalized copy is written only inside the benchmark.
        data = pd.read_csv(path, comment="#", names=["date", "concentration"])
    return data["date"].to_numpy(dtype=float), data["concentration"].to_numpy(dtype=float)


def _manifest_path(path: Path) -> str:
    return path.relative_to(BENCHMARK_ROOT).as_posix() if path.is_relative_to(BENCHMARK_ROOT) else str(path)


def generate(config_path: Path = DEFAULT_CONFIG, output_dir: Path = OUTPUT_DIR) -> dict:
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    observation_year = float(config["observation_year"])
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_cases = []

    for case in expanded_cases(config):
        noise = case["noise"]
        if noise["kind"] not in {"none", "gaussian_relative"}:
            raise ValueError(f"Type de bruit non pris en charge: {noise['kind']}")
        rng = np.random.default_rng(int(noise["seed"])) if noise["kind"] != "none" else None
        rows = []
        for tracer in config["tracers"]:
            source = REPO_ROOT / tracer["recharge"]
            dates, concentrations = _chronicle(source)

            def input_function(year):
                return np.interp(year, dates, concentrations, left=0.0, right=concentrations[-1])

            value, covered_mass = forward(
                case["model"], case["true_parameters"], observation_year,
                input_function, observation_year - dates[0], observation_year - dates,
            )
            noise_fraction = (
                float(rng.normal(0.0, float(noise["relative_standard_deviation"])))
                if rng is not None else 0.0
            )
            observed = value * (1.0 + noise_fraction)
            rows.append({
                "case_id": case["case_id"], "tracer": tracer["name"],
                "unit": tracer["unit"], "observation_year": f"{observation_year:.12f}",
                "model": case["model"],
                "true_parameters": json.dumps(case["true_parameters"], sort_keys=True),
                "true_concentration": f"{value:.12f}",
                "observed_concentration": f"{observed:.12f}",
                "covered_distribution_mass": f"{covered_mass:.12f}",
                "recharge_path": tracer["recharge"],
                "recharge_sha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
                "noise_kind": noise["kind"],
                "noise_seed": "" if rng is None else str(noise["seed"]),
                "noise_relative_standard_deviation": (
                    "" if rng is None else f"{float(noise['relative_standard_deviation']):.12f}"
                ),
                "noise_realization_fraction": f"{noise_fraction:.12f}",
            })
        output_path = output_dir / f"{case['case_id']}.csv"
        with output_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        manifest_cases.append({
            "case_id": case["case_id"], "row_count": len(rows),
            "output": _manifest_path(output_path),
            "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest().upper(),
        })

    # TracerLPM Example 1 exposes two neutralisable columns (SF6 and NO3-N).
    # The one-parameter pilot aliases CFC-11 to the SF6 slot; only the numeric
    # history matters to the stable-tracer convolution.
    cfc11 = next(item for item in config["tracers"] if item["name"] == "cfc11")
    dates, concentrations = _chronicle(REPO_ROOT / cfc11["recharge"])
    tracerlpm_input = output_dir / "tracerlpm-emm-pilot-cfc11-as-sf6.csv"
    with tracerlpm_input.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["date", "concentration"])
        writer.writerows(zip(dates, concentrations))

    chronicles = {}
    for tracer in config["tracers"]:
        chronicles[tracer["name"]] = _chronicle(REPO_ROOT / tracer["recharge"])
    common_dates = np.unique(np.concatenate([item[0] for item in chronicles.values()]))
    multitracer_input = output_dir / "tracerlpm-emm-pilot-three-cfcs.csv"
    with multitracer_input.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["date", "cfc11", "cfc12", "cfc113"])
        writer.writerows(
            [date, *[
                np.interp(date, chronicles[name][0], chronicles[name][1], left=0.0,
                          right=chronicles[name][1][-1])
                for name in ("cfc11", "cfc12", "cfc113")
            ]]
            for date in common_dates
        )

    # Generic history used by workbooks that expose every configured tracer
    # natively (for example the qualified CFC-11/CFC-12/CFC-113/SF6 copy).
    tracer_names = [item["name"] for item in config["tracers"]]
    native_input = output_dir / "tracerlpm-input-history.csv"
    with native_input.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["date", *tracer_names])
        writer.writerows(
            [date, *[
                np.interp(date, chronicles[name][0], chronicles[name][1], left=0.0,
                          right=chronicles[name][1][-1])
                for name in tracer_names
            ]]
            for date in common_dates
        )

    normalized = []
    for tracer in [item for item in config["tracers"] if item["name"] == "cfc12"]:
        source = REPO_ROOT / tracer["recharge"]
        normalized_dates, normalized_values = _chronicle(source)
        target = output_dir / f"normalized-{tracer['name']}.csv"
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["date", "concentration"])
            writer.writerows(zip(normalized_dates, normalized_values))
        normalized.append({
            "name": tracer["name"], "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
            "path": _manifest_path(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest().upper(),
        })
        tracer_dir = output_dir / "normalized_tracers" / tracer["name"]
        tracer_dir.mkdir(parents=True, exist_ok=True)
        shutil_target = tracer_dir / "recharge.csv"
        shutil_target.write_bytes(target.read_bytes())
        (tracer_dir / f"{tracer['name']}.yaml").write_text(
            "unit: pptv\nrecharge: true\n", encoding="utf-8", newline="\n"
        )

    manifest = {
        "campaign_id": config["campaign_id"],
        "generator": "independent 8-point Gauss-Legendre quadrature per recharge interval",
        "config_sha256": hashlib.sha256(config_bytes).hexdigest().upper(),
        "cases": manifest_cases,
        "tracerlpm_pilot_input": {
            "alias": "cfc11 -> SF6",
            "path": _manifest_path(tracerlpm_input),
            "sha256": hashlib.sha256(tracerlpm_input.read_bytes()).hexdigest().upper(),
        },
        "tracerlpm_multitracer_input": {
            "aliases": {"cfc11": "SF6", "cfc12": "3H", "cfc113": "NO3-N"},
            "path": _manifest_path(multitracer_input),
            "sha256": hashlib.sha256(multitracer_input.read_bytes()).hexdigest().upper(),
        },
        "normalized_only_tracers": normalized,
    }
    manifest_text = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    (output_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8", newline="\n")
    (output_dir / f"manifest-{config['campaign_id']}.yaml").write_text(
        manifest_text, encoding="utf-8", newline="\n"
    )
    return manifest


if __name__ == "__main__":
    print(yaml.safe_dump(generate(), sort_keys=False), end="")
