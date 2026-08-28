# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Presentation and serialization boundary for calibration runs.

Calibration algorithms produce in-memory diagnostics and joint LPM sample
tables. This module decides which standard files and plots correspond to each
method, keeping filesystem layout and presentation logic out of numerical
loops. Posterior histograms may also be copied into a named prior directory for
an explicit multi-stage calibration workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyages.data_io.lpm_distribution import (
    write_distribution,
    write_histograms,
    write_statistics,
)
from pyages.lpm.plotting.sample_diagnostics import plot_parameter_diagnostics
from pyages.lpm.reporting import print_parameter_comparison

if TYPE_CHECKING:
    from pyages.calibration.methods.base import CalibrationMethod
    from pyages.calibration.problem import CalibrationProblem
    from pyages.config.runtime import DisplayOptions
    from pyages.lpm.samples.table import LpmSampleTable


def posterior_directory(
    reference_file: str | Path,
    *,
    parent_levels: int = 5,
    subdirectory: str = "",
) -> Path:
    """Return the shared directory used to reuse posteriors as priors.

    ``reference_file`` anchors the calculation and ``parent_levels`` selects a
    stable ancestor before ``prior_distributions`` is appended. The directory
    is created here because callers immediately serialize into it.
    """
    path = Path(reference_file).resolve()
    if parent_levels < 1:
        raise ValueError("parent_levels must be positive")
    try:
        root = path.parents[parent_levels - 1]
    except IndexError as exc:
        raise ValueError(
            f"parent_levels={parent_levels} goes above the root for {path}"
        ) from exc
    destination = root / "prior_distributions"
    if subdirectory:
        destination /= subdirectory
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def posterior_file_stem(case: str, concentration_error: float, lpm_type: str) -> str:
    """Build the filename stem used by the Ploemeur prior pipeline."""
    return f"{case}_err_{concentration_error}_lpm_{lpm_type}"


def write_key_values(path: str | Path, values: dict[str, Any]) -> None:
    """Write ordered scalar metadata as a tab-separated key/value file."""
    with Path(path).open("w", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}\t{value}\n")


def display_calibrated_models(
    method: CalibrationMethod,
    problem: CalibrationProblem,
    results: LpmSampleTable,
    display_options: DisplayOptions,
    reference=None,
) -> None:
    """Render the method-appropriate calibrated model comparison.

    Deterministic Simplex runs report their best model against a reference in
    text. Sample-producing methods use distribution diagnostics when figures
    are enabled. Display choices never alter stored calibration results.
    """
    if method.method in {"Simplex", "Simplex_multi_start"}:
        if display_options.text and reference is not None:
            lpm = results.best_model()
            if lpm is not None:
                print_parameter_comparison(lpm, reference)
        return
    if (
        method.method
        in {
            "forward_uncertainty_quantification",
            "Metropolis_Hastings",
        }
        and display_options.figure
    ):
        plot_parameter_diagnostics(
            results,
            self_method=method.method,
            lpm_reference=reference,
            directory=problem.display_options.directory,
        )


def write_calibrated_result(
    method: CalibrationMethod,
    problem: CalibrationProblem,
    results: LpmSampleTable,
    *,
    prior_file: str | None = None,
    prior_folder: str = "",
) -> None:
    """Write the standard result files for one calibration method.

    Every method writes configuration and scalar run diagnostics. Methods that
    produce more than one meaningful sample also write the joint distribution,
    marginal histograms, and statistics. Metropolis--Hastings may additionally
    export histograms for an explicitly requested posterior-to-prior pipeline.
    """
    base_directory = Path(problem.display_options.directory)
    base_directory.mkdir(parents=True, exist_ok=True)
    method.write_parameters(base_directory / "parameters_calibration.txt")
    method.write_results(base_directory / "results_calibration.txt")
    # A single deterministic optimum has no empirical distribution to export.
    if method.method != "Simplex":
        write_distribution(results, base_directory / "lpm_dist_calibrated.txt")
        write_histograms(results, base_directory / "lpm_histo_calibrated.txt")
        write_statistics(results, base_directory / "lpm_stats_calibrated.txt")
    # Posterior reuse is opt-in and restricted to the Bayesian workflow.
    if method.method == "Metropolis_Hastings" and prior_file is not None:
        destination = posterior_directory(
            problem.display_options.directory,
            parent_levels=5,
            subdirectory=prior_folder,
        )
        write_histograms(results, destination / f"{prior_file}.txt")


__all__ = [
    "display_calibrated_models",
    "posterior_directory",
    "posterior_file_stem",
    "write_calibrated_result",
    "write_key_values",
]
