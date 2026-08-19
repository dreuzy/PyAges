"""Build TracerLPM fit cases from the immutable noisy observation CSV files."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import OUTPUT_DIR, expanded_cases

DEFAULT_CONFIG = BENCHMARK_ROOT / "configs" / "inversion-noisy-campaign.yaml"
DEFAULT_OUTPUT = BENCHMARK_ROOT / "configs" / "tracerlpm-inversion-noisy-campaign.yaml"


def prepare(
    config_path: Path = DEFAULT_CONFIG,
    output_path: Path = DEFAULT_OUTPUT,
    case_ids: set[str] | None = None,
) -> list[dict]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    tracerlpm = config.get("tracerlpm", {})
    target_tracers = tracerlpm.get("target_tracers", ["SF6", "3H", "NO3-N"])
    source_columns = tracerlpm.get(
        "source_columns", {"SF6": "cfc11", "3H": "cfc12", "NO3-N": "cfc113"}
    )
    history_name = tracerlpm.get("input_history", "tracerlpm-emm-pilot-three-cfcs.csv")
    history = OUTPUT_DIR / history_name
    history_hash = hashlib.sha256(history.read_bytes()).hexdigest().upper()
    cases = []
    for source in expanded_cases(config):
        if case_ids is not None and source["case_id"] not in case_ids:
            continue
        with (OUTPUT_DIR / f"{source['case_id']}.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            observations = {
                row["tracer"]: float(row["observed_concentration"])
                for row in csv.DictReader(stream)
            }
        epm = source["model"] == "EPM"
        secondary_key = "eta" if epm else "DP"
        secondary_offset = 1.0 if epm else 0.0
        true_model_parameter = (
            float(source["true_parameters"][secondary_key]) - secondary_offset
        )
        initial_pairs = [
            [float(value) for value in pair] for pair in source["initial_values"]
        ]
        cases.append(
            {
                "case_id": f"{source['case_id']}-tracerlpm",
                "sample": tracerlpm.get("sample", "PSW-1-17/08/2004"),
                "observation_year": float(config["observation_year"]),
                "tracerlpm_effective_observation_year": float(
                    config["observation_year"]
                ),
                "model1": source["model"],
                "model2": source["model"],
                "model_parameter": true_model_parameter,
                "x_axis": tracerlpm.get("x_axis", target_tracers[0]),
                "y_axis": tracerlpm.get("y_axis", target_tracers[-1]),
                "input_history": {
                    "path": f"../observations/{history_name}",
                    "sha256": history_hash,
                    "target_tracers": target_tracers,
                    "source_columns": source_columns,
                    "before": 0.0,
                    "after": "hold_last",
                },
                "fit": {
                    "sample": tracerlpm.get("sample", "PSW-1-17/08/2004"),
                    "model": source["model"],
                    "observations": {
                        target: observations[source_columns[target]]
                        for target in target_tracers
                    },
                    "initial_ages": [pair[0] for pair in initial_pairs],
                    "initial_model_parameters": [
                        pair[1] - secondary_offset for pair in initial_pairs
                    ],
                    "age_lower": float(source["bounds"]["tau"][0]),
                    "age_upper": float(source["bounds"]["tau"][1]),
                    "model_parameter_lower": float(source["bounds"][secondary_key][0])
                    - secondary_offset,
                    "model_parameter_upper": float(source["bounds"][secondary_key][1])
                    - secondary_offset,
                },
            }
        )
    output_path.write_text(
        "# Généré depuis inversion-noisy-campaign.yaml et les CSV d'observation.\n"
        + yaml.safe_dump(cases, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    return cases


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    print(
        f"{len(prepare(args.config, args.output, set(args.case_id) or None))} cas TracerLPM générés"
    )
