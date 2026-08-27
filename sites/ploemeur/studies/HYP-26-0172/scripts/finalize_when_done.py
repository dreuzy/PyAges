# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Wait for a campaign, then build all derived products and figures."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .study_common import REPO_ROOT, profile_results_root, validate_profile


def write_status(path: Path, state: str, **extra) -> None:
    value = {
        "state": state,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=validate_profile, default="production")
    parser.add_argument("--poll-seconds", type=float, default=60.0)
    args = parser.parse_args()
    results_root = profile_results_root(args.profile)
    status_path = results_root / "supervisor_status.json"
    finalizer_status = results_root / "finalizer_status.json"
    results_root.mkdir(parents=True, exist_ok=True)
    write_status(
        finalizer_status,
        "waiting",
        supervisor_status=str(status_path.relative_to(REPO_ROOT)),
    )
    while True:
        if status_path.is_file():
            status = json.loads(status_path.read_text(encoding="utf-8"))
            state = status.get("state")
            if state == "completed":
                break
            if state == "completed_with_failures":
                write_status(
                    finalizer_status,
                    "blocked",
                    reason="one or more campaign experiments failed",
                )
                return 1
        time.sleep(args.poll_seconds)
    write_status(finalizer_status, "building")
    command = [
        sys.executable,
        "-m",
        "sites.ploemeur.studies.HYP-26-0172.postprocessing.build_products",
        "--profile",
        args.profile,
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=False)
    write_status(
        finalizer_status,
        "completed" if result.returncode == 0 else "failed",
        return_code=result.returncode,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
