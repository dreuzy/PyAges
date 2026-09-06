# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run the documented quick or full local contributor checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]


class CheckStep(NamedTuple):
    """One named subprocess in a contributor check profile."""

    label: str
    command: tuple[str, ...]


QUICK_STEPS = (
    CheckStep("Dependency consistency", (sys.executable, "-m", "pip", "check")),
    CheckStep("Ruff lint", (sys.executable, "-m", "ruff", "check", ".")),
    CheckStep(
        "Ruff format",
        (sys.executable, "-m", "ruff", "format", "--check", "."),
    ),
    CheckStep("Progressive typing", (sys.executable, "-m", "pyright")),
    CheckStep(
        "Qualified docstrings",
        (sys.executable, "-m", "scripts.maintenance.check_qualified_docstrings"),
    ),
    CheckStep(
        "Licensing metadata",
        (sys.executable, "-m", "scripts.maintenance.check_licensing"),
    ),
    CheckStep(
        "Architecture boundaries",
        (sys.executable, "-m", "scripts.maintenance.check_architecture"),
    ),
)

FULL_ONLY_STEPS = (
    CheckStep(
        "Generated test inventory",
        (
            sys.executable,
            "-m",
            "scripts.maintenance.generate_test_inventory",
            "--check",
        ),
    ),
    CheckStep("Standard tests", (sys.executable, "run_tests.py", "standard")),
    CheckStep(
        "Strict documentation build",
        (
            sys.executable,
            "-m",
            "sphinx",
            "-E",
            "-a",
            "-W",
            "--keep-going",
            "-b",
            "html",
            "docs",
            "docs/_build/html",
        ),
    ),
)


def steps_for(profile: str) -> tuple[CheckStep, ...]:
    """Return the ordered steps belonging to one documented profile."""
    if profile == "quick":
        return QUICK_STEPS
    if profile == "full":
        return QUICK_STEPS + FULL_ONLY_STEPS
    raise ValueError(f"unknown developer-check profile: {profile}")


def run_checks(steps: Sequence[CheckStep]) -> int:
    """Run checks in order and stop at the first failure."""
    for index, step in enumerate(steps, start=1):
        print(f"[{index}/{len(steps)}] {step.label}", flush=True)
        print("  " + " ".join(step.command), flush=True)
        completed = subprocess.run(step.command, cwd=ROOT, check=False)
        if completed.returncode:
            print(
                f"Developer checks stopped: {step.label} failed "
                f"with exit code {completed.returncode}.",
                file=sys.stderr,
            )
            return completed.returncode
    print(f"All {len(steps)} developer checks passed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the profile and run its contributor checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=("quick", "full"),
        help="quick checks static contracts; full also runs inventory, tests, and docs",
    )
    args = parser.parse_args(argv)
    return run_checks(steps_for(args.profile))


if __name__ == "__main__":
    raise SystemExit(main())
