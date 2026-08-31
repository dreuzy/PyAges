# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Enforce docstring quality on the qualified calibration/runtime surface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALIFIED_PATHS = (
    "pyages/calibration/methods/mh",
    "pyages/calibration/problem.py",
    "pyages/calibration/sampling_schedule.py",
    "pyages/calibration/target_signature.py",
    "pyages/config/models.py",
    "pyages/data_io/mh_results.py",
    "pyages/workflows/runtime",
    "pyages/workflows/single_date/runner.py",
    "pyages/workflows/temporal/runner.py",
)


def main() -> int:
    """Run Ruff's pydocstyle rules on the progressively qualified paths."""
    completed = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "D", *QUALIFIED_PATHS],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
