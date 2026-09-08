# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run, postprocess, and validate the complete HYP-26-0172 study."""

from __future__ import annotations

import argparse
import subprocess
import sys

from .study_common import REPO_ROOT, profile_results_root, validate_profile

MODULE_ROOT = "sites.ploemeur.studies.HYP-26-0172"


def parse_args() -> argparse.Namespace:
    """Parse complete-campaign orchestration options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="number of concurrent six-process experiments (1 or 2)",
    )
    parser.add_argument(
        "--profile",
        type=validate_profile,
        default="production",
        help="campaign profile; 'smoke' runs an isolated 100-step campaign",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="allow the simulation stage to reuse existing run directories",
    )
    return parser.parse_args()


def pipeline_commands(
    *, profile: str, max_workers: int, resume: bool
) -> list[tuple[str, list[str]]]:
    """Return the ordered commands for a complete study campaign."""
    supervisor = [
        sys.executable,
        "-m",
        f"{MODULE_ROOT}.scripts.supervise_runs",
        "--profile",
        profile,
        "--max-workers",
        str(max_workers),
    ]
    if resume:
        supervisor.append("--resume")

    figures = profile_results_root(profile) / "figures"
    return [
        (
            "study validation",
            [sys.executable, "-m", f"{MODULE_ROOT}.scripts.validate_study"],
        ),
        ("simulations", supervisor),
        (
            "postprocessing",
            [
                sys.executable,
                "-m",
                f"{MODULE_ROOT}.postprocessing.build_products",
                "--profile",
                profile,
            ],
        ),
        (
            "final figure validation",
            [
                sys.executable,
                "-m",
                f"{MODULE_ROOT}.postprocessing.validate_submission_figures",
                "--directory",
                str(figures),
            ],
        ),
    ]


def run_pipeline(*, profile: str, max_workers: int, resume: bool = False) -> int:
    """Execute every campaign stage in order and stop at the first failure."""
    for stage, command in pipeline_commands(
        profile=profile, max_workers=max_workers, resume=resume
    ):
        print(f"\n=== {stage} ===", flush=True)
        result = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if result.returncode != 0:
            print(
                f"HYP-26-0172 stopped during {stage} "
                f"(return code {result.returncode}).",
                file=sys.stderr,
            )
            return result.returncode
    print("\nHYP-26-0172 completed and final figures validated.")
    return 0


def main() -> int:
    """Run the complete study for the requested campaign profile."""
    args = parse_args()
    return run_pipeline(
        profile=args.profile,
        max_workers=args.max_workers,
        resume=args.resume,
    )


if __name__ == "__main__":
    raise SystemExit(main())
