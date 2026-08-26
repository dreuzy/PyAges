# -*- coding: utf-8 -*-
"""
Run the synthetic single-date recovery example end to end.
"""

from __future__ import annotations

from pathlib import Path

from examples.synthetic.lpm_recovery_single_date.synthetic_case import (
    build_truth_aware_figures,
    generate_synthetic_case,
)
from pyage.workflows.single_date import run_single_date


def main(force_inline: bool = False) -> Path:
    """Generate the synthetic data, run the calibration and build summary figures."""
    case = generate_synthetic_case()
    results_dir = run_single_date(case.paths.params_path, force_inline=force_inline)
    recovery = build_truth_aware_figures(
        results_dir=results_dir,
        truth_payload=case.truth_payload,
        dataset_path=case.paths.dataset_path,
    )
    print("Synthetic data regenerated in:", case.paths.dataset_path)
    print("Ground truth stored in:", case.paths.truth_path)
    print("Results written to:", results_dir)
    print(recovery.to_string(index=False))
    return results_dir


if __name__ == "__main__":
    main()
