# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Create balanced TracerLPM queues containing only missing robustness cases."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from .check_robustness_progress import RUN_OUTPUT
from .generate_inputs import BENCHMARK_ROOT
from .prepare_robustness_study import OUTPUT_ALL, _write

DEFAULT_PREFIX = "tracerlpm-robustness-missing"
PREFIX_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def successful_case_ids(run_output: Path) -> set[str]:
    successful: set[str] = set()
    for path in run_output.glob("robust-*-tracerlpm-*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        case_id = report.get("caseId")
        if case_id and report.get("status") == "success":
            successful.add(case_id)
    return successful


def partition_cases(
    cases: list[dict], successful: set[str], shard_count: int
) -> list[list[dict]]:
    if shard_count < 1:
        raise ValueError("shard_count doit être supérieur ou égal à 1")
    identifiers = [case["case_id"] for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("La file complète contient des identifiants en double")
    remaining = [case for case in cases if case["case_id"] not in successful]
    active_shards = min(shard_count, len(remaining))
    if active_shards == 0:
        return []
    base, extra = divmod(len(remaining), active_shards)
    result: list[list[dict]] = []
    start = 0
    for index in range(active_shards):
        size = base + (1 if index < extra else 0)
        result.append(remaining[start : start + size])
        start += size
    return result


def build(
    shard_count: int = 6,
    prefix: str = DEFAULT_PREFIX,
    all_cases_path: Path = OUTPUT_ALL,
    run_output: Path = RUN_OUTPUT,
    config_directory: Path | None = None,
) -> dict:
    if not PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError(
            "prefix doit contenir uniquement des minuscules, chiffres et tirets"
        )
    config_directory = config_directory or BENCHMARK_ROOT / "configs"
    cases = yaml.safe_load(all_cases_path.read_text(encoding="utf-8"))
    successful = successful_case_ids(run_output)
    expected = {case["case_id"] for case in cases}
    shards = partition_cases(cases, successful, shard_count)
    manifest = {
        "expected": len(expected),
        "valid": len(expected.intersection(successful)),
        "remaining": sum(len(shard) for shard in shards),
        "shards": [],
    }
    for index, shard in enumerate(shards, start=1):
        path = config_directory / f"{prefix}-shard{index}.yaml"
        _write(path, shard, f"la reprise de robustesse, segment {index}")
        manifest["shards"].append(
            {
                "path": str(path.resolve()),
                "count": len(shard),
                "first": shard[0]["case_id"],
                "last": shard[-1]["case_id"],
            }
        )
    campaign_directory = run_output / "campaign"
    campaign_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = campaign_directory / f"{prefix}-manifest.json"
    manifest["manifest_path"] = str(manifest_path.resolve())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=6)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.shards, arguments.prefix), ensure_ascii=False))


if __name__ == "__main__":
    main()
