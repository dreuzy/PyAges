# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run enabled experiments with bounded experiment-level parallelism."""

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
import threading
from datetime import datetime, timezone

from .study_common import (
    REPO_ROOT,
    load_matrix,
    profile_results_root,
    validate_profile,
    write_json,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--profile", type=validate_profile, default="production")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_workers <= 2:
        raise ValueError(
            "This 12-logical-core machine supports at most 2 concurrent six-process runs"
        )
    rows = [row for row in load_matrix() if row["enabled"].lower() == "true"]
    if args.family:
        rows = [row for row in rows if row["family"] in args.family]
    results_root = profile_results_root(args.profile)
    logs = results_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    status_path = results_root / "supervisor_status.json"
    lock = threading.Lock()
    status = {
        "started_at_utc": utc_now(),
        "finished_at_utc": None,
        "max_workers": args.max_workers,
        "profile": args.profile,
        "state": "running",
        "experiments": {row["experiment_id"]: {"state": "queued"} for row in rows},
    }

    def persist() -> None:
        with lock:
            write_json(status_path, status)

    def run(row: dict[str, str]) -> int:
        experiment_id = row["experiment_id"]
        stdout_path = logs / f"{experiment_id}.stdout.log"
        stderr_path = logs / f"{experiment_id}.stderr.log"
        command = [
            sys.executable,
            "-m",
            "sites.ploemeur.studies.HYP-26-0172.scripts.run_matrix",
            "--experiment-id",
            experiment_id,
            "--profile",
            args.profile,
            "--execute",
        ]
        if args.resume:
            command.append("--resume")
        with lock:
            status["experiments"][experiment_id] = {
                "state": "running",
                "started_at_utc": utc_now(),
                "stdout": str(stdout_path.relative_to(REPO_ROOT)),
                "stderr": str(stderr_path.relative_to(REPO_ROOT)),
            }
            write_json(status_path, status)
        with (
            stdout_path.open("a", encoding="utf-8") as stdout,
            stderr_path.open("a", encoding="utf-8") as stderr,
        ):
            result = subprocess.run(
                command, cwd=REPO_ROOT, stdout=stdout, stderr=stderr, check=False
            )
        with lock:
            status["experiments"][experiment_id].update(
                state="completed" if result.returncode == 0 else "failed",
                return_code=result.returncode,
                finished_at_utc=utc_now(),
            )
            write_json(status_path, status)
        return result.returncode

    persist()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        return_codes = list(pool.map(run, rows))
    status["state"] = (
        "completed"
        if all(code == 0 for code in return_codes)
        else "completed_with_failures"
    )
    status["finished_at_utc"] = utc_now()
    persist()
    return 0 if all(code == 0 for code in return_codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
