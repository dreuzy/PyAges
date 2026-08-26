"""Presentation and file output helpers for calibration runs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyage.data_io.lpm_distribution import (
    write_distribution,
    write_histograms,
    write_statistics,
)
from pyage.lpm.distribution_plotting import display_parameter_distributions
from pyage.lpm.presentation import display_parameters

if TYPE_CHECKING:
    from pyage.calibration.methods.base import CalibrationMethod
    from pyage.calibration.problem import CalibrationProblem
    from pyage.config.runtime import DisplayOptions
    from pyage.lpm.core.lpm_dist import LpmDist


def posterior_directory(
    reference_file: str | Path,
    *,
    parent_levels: int = 5,
    subdirectory: str = "",
) -> Path:
    """Return the shared directory used to reuse posteriors as priors."""
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
    """Write a small tab-separated key/value file."""
    with Path(path).open("w", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}\t{value}\n")


def display_calibrated_models(
    method: CalibrationMethod,
    problem: CalibrationProblem,
    results: LpmDist,
    display_options: DisplayOptions,
    reference=None,
) -> None:
    """Render the method-appropriate calibrated model comparison."""
    if method.method in {"Simplex", "Simplex_multi_start"}:
        if display_options.text and reference is not None:
            lpm = results.best_model()
            if lpm is not None:
                display_parameters(lpm, reference)
        return
    if (
        method.method
        in {
            "forward_uncertainty_quantification",
            "Metropolis_Hastings",
        }
        and display_options.figure
    ):
        display_parameter_distributions(
            results,
            self_method=method.method,
            lpm_reference=reference,
            directory=problem.display_options.directory,
        )


def write_calibrated_result(
    method: CalibrationMethod,
    problem: CalibrationProblem,
    results: LpmDist,
    *,
    prior_file: str | None = None,
    prior_folder: str = "",
) -> None:
    """Write the standard result files for one calibration method."""
    base_directory = Path(problem.display_options.directory)
    base_directory.mkdir(parents=True, exist_ok=True)
    method.write_parameters(base_directory / "parameters_calibration.txt")
    method.write_results(base_directory / "results_calibration.txt")
    if method.method != "Simplex":
        write_distribution(results, base_directory / "lpm_dist_calibrated.txt")
        write_histograms(results, base_directory / "lpm_histo_calibrated.txt")
        write_statistics(results, base_directory / "lpm_stats_calibrated.txt")
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
