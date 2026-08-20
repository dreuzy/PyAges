"""Presentation and file output helpers for calibration runs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    """Build the historical prior/posterior filename stem."""
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
    if method.method in {"Simplex", "Simplex_init_multipes"}:
        if display_options.text and reference is not None:
            exists, lpm = results.get_best_lpm()
            if exists:
                lpm.display_parameters(reference)
        return
    if (
        method.method
        in {
            "forward_uncertainty_quantification",
            "Metropolis_Hastings",
        }
        and display_options.figure
    ):
        results.display_parameters_dist(
            self_method=method.method,
            lpm_reference=reference,
            bins=100,
            directory=problem.display_options.directory,
        )


def write_calibrated_result(
    method: CalibrationMethod,
    problem: CalibrationProblem,
    results: LpmDist,
    *,
    prior_file: str = "none",
    prior_folder: str = "",
) -> None:
    """Write the standard result files for one calibration method."""
    base_directory = Path(problem.display_options.directory)
    base_directory.mkdir(parents=True, exist_ok=True)
    method.write_parameters(base_directory / "parameters_calibration.txt")
    method.write_results(base_directory / "results_calibration.txt")
    if method.method != "Simplex":
        results.write_dist(base_directory / "lpm_dist_calibrated.txt")
        results.write_histograms(base_directory / "lpm_histo_calibrated.txt")
        results.write_stats(base_directory / "lpm_stats_calibrated.txt")
    if method.method == "Metropolis_Hastings":
        destination = posterior_directory(
            problem.display_options.directory,
            parent_levels=5,
            subdirectory=prior_folder,
        )
        results.write_histograms(destination / f"{prior_file}.txt")


__all__ = [
    "display_calibrated_models",
    "posterior_directory",
    "posterior_file_stem",
    "write_calibrated_result",
    "write_key_values",
]
