# -*- coding: utf-8 -*-
"""
Run the synthetic single-date recovery example end to end.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from examples.synthetic.lpm_recovery_single_date.synthetic_case import (
    build_truth_aware_figures,
    case_paths,
    generate_synthetic_case,
    load_ground_truth,
)
from pyage.workflows.single_date import run_single_date


def main(force_inline: bool = False, *, regenerate: bool = False) -> Path:
    """Run the stored teaching case and optionally regenerate its inputs."""
    paths = case_paths()
    if regenerate:
        case = generate_synthetic_case()
        truth_payload = case.truth_payload
        print("Synthetic data regenerated in:", paths.dataset_path)
        print("Ground truth stored in:", paths.truth_path)
    else:
        truth_payload = load_ground_truth(paths.truth_path)

    results_dir = run_single_date(paths.params_path, force_inline=force_inline)
    recovery = build_truth_aware_figures(
        results_dir=results_dir,
        truth_payload=truth_payload,
        dataset_path=paths.dataset_path,
    )
    print("Results written to:", results_dir)
    print(recovery.to_string(index=False))
    return results_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate the versioned synthetic inputs before calibration.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Use the inline plotting backend.",
    )
    args = parser.parse_args()
    main(force_inline=args.inline, regenerate=args.regenerate)
