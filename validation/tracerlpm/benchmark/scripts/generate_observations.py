"""Create deterministic synthetic inversion observations from forward truth."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import yaml

from .generate_inputs import BENCHMARK_ROOT, DEFAULT_CONFIG
from .generate_references import DEFAULT_OUTPUT as DEFAULT_FORWARD_REFERENCE


DEFAULT_OUTPUT = BENCHMARK_ROOT / "references" / "synthetic_observations.csv"
DEFAULT_MANIFEST = BENCHMARK_ROOT / "references" / "observations_manifest.yaml"


def _noise_realizations(noise_config: dict) -> list[tuple[str, float, int | None]]:
    result = [("none", 0.0, None)]
    low = noise_config["low_deterministic"]
    result.append(("low_deterministic", float(low["relative_standard_deviation"]), int(low["seed"])))
    repeated = noise_config["repeated"]
    result.extend(
        (f"repeated_{index + 1}", float(repeated["relative_standard_deviation"]), int(seed))
        for index, seed in enumerate(repeated["seeds"])
    )
    return result


def generate(config_path: Path = DEFAULT_CONFIG, forward_path: Path = DEFAULT_FORWARD_REFERENCE, output_path: Path = DEFAULT_OUTPUT, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    with forward_path.open(encoding="utf-8", newline="") as stream:
        truth_rows = list(csv.DictReader(stream))
    regimes = _noise_realizations(config["noise"])
    rng_by_seed = {seed: np.random.default_rng(seed) for _, _, seed in regimes if seed is not None}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = ["case_id", "input", "model", "true_parameters", "observation_year", "noise_regime", "seed", "relative_standard_deviation", "true_concentration", "observed_concentration"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        count = 0
        for truth_index, truth in enumerate(truth_rows):
            true_value = float(truth["concentration"])
            for regime, relative_std, seed in regimes:
                factor = 1.0 if seed is None else 1.0 + float(rng_by_seed[seed].normal(0.0, relative_std))
                observed = true_value * factor
                writer.writerow({
                    "case_id": f"truth-{truth_index + 1:04d}-{regime}",
                    "input": truth["input"],
                    "model": truth["model"],
                    "true_parameters": truth["parameters"],
                    "observation_year": truth["observation_year"],
                    "noise_regime": regime,
                    "seed": "" if seed is None else seed,
                    "relative_standard_deviation": f"{relative_std:.12f}",
                    "true_concentration": f"{true_value:.12f}",
                    "observed_concentration": f"{observed:.12f}",
                })
                count += 1
    manifest = {
        "campaign_id": config["campaign_id"],
        "kind": "synthetic_inversion_observations",
        "truth_row_count": len(truth_rows),
        "noise_realization_count": len(regimes),
        "observation_row_count": count,
        "forward_reference_sha256": hashlib.sha256(forward_path.read_bytes()).hexdigest().upper(),
        "synthetic_observations_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest().upper(),
        "noise_model": "multiplicative Gaussian; observed=true*(1+N(0, relative_standard_deviation))",
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    print(yaml.safe_dump(generate(), sort_keys=False), end="")
