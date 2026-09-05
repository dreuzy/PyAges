# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Enforce docstrings on qualified library and reproducibility code.

The project does not require exhaustive API prose in every historical script.
It does, however, require it in the public calibration/runtime core and in the
maintained helpers that define scientific evidence, diagnostics, or published
figures.  This explicit list lets that stricter surface grow progressively.
"""

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
    "scripts/common/mcmc_diagnostics.py",
    "scripts/common/provenance.py",
    "scripts/common/reporting.py",
    "scripts/qualification/_archive_contract.py",
    "scripts/qualification/_archive_evidence.py",
    "scripts/qualification/_archive_verification.py",
    "scripts/qualification/build_ci_multichain_archive.py",
    "scripts/qualification/build_multichain_archive.py",
    "examples/natural/ploemeur_temporal/reproduction_diagnostics.py",
    "examples/natural/holten/holten_four_bin_plots.py",
    "sites/ploemeur/studies/HYP-26-0172/postprocessing/build_products.py",
    "sites/ploemeur/studies/HYP-26-0172/postprocessing/product_extraction.py",
    "sites/ploemeur/studies/HYP-26-0172/postprocessing/summary_figures.py",
    "sites/ploemeur/studies/HYP-26-0172/scripts/run_matrix.py",
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
