"""Run the 60-case PyAge Monte-Carlo campaign in parallel worker processes."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import yaml

from .generate_inputs import BENCHMARK_ROOT
from .generate_inversion_pilot import OUTPUT_DIR, expanded_cases, generate
from .invert_pyage_pilot import invert


CONFIG = BENCHMARK_ROOT / "configs" / "inversion-monte-carlo-01.yaml"


def _run_one(case_id: str, config_path: Path) -> dict:
    return invert(config_path=config_path, observation_dir=OUTPUT_DIR, case_ids={case_id})["cases"][0]


def run(config_path: Path = CONFIG, workers: int = 4) -> dict:
    generate(config_path=config_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    case_ids = [case["case_id"] for case in expanded_cases(config)]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_one, case_id, config_path): case_id for case_id in case_ids}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{len(results)}/{len(case_ids)} {result['case_id']}", flush=True)
    return {"campaign_id": config["campaign_id"], "case_count": len(results),
            "successful": sum(result["optimizer_success"] for result in results)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.workers), indent=2))
