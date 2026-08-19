"""Path helpers for the Ploemeur workflow."""

from pathlib import Path

import pyage.calibration.utils.calibration_core as calbas
from pyage.config.paths import result_subdirectory, timestamp_name
from sites.ploemeur.observations import ploemeur as ploemeur_obs


def results_folder(file_root: str, base_dir: str | None = None):
    """Return (dir_out, dir_root, date_file) for a results root."""
    if base_dir:
        dir_root = result_subdirectory(base_dir, file_root)
        date_file = timestamp_name()
        directory_results = result_subdirectory(dir_root, date_file)
        return directory_results, dir_root, date_file
    return ploemeur_obs.ploemeur_results_folder(file_root)


def prior_file_path(
    dir_out: str,
    prior_corresp: dict[str, str],
    well_date: str,
    conc_error_rel: float,
    lpm: str,
    prior_folder: str,
) -> str:
    """Build the prior file path for a given well/date and model."""
    temp_file = calbas.file_prior_posterior(
        prior_corresp[well_date], conc_error_rel, lpm
    )
    temp_folder = calbas.folder_prior_posterior(
        dir_out, stageup=-2, folder_prior=prior_folder
    )
    return str(Path(temp_folder) / temp_file)


def calibrated_prior_name(well_date: str, conc_error_rel: float, lpm_type: str) -> str:
    """Build the filename for a calibrated prior from a run."""
    return calbas.file_prior_posterior(well_date, conc_error_rel, lpm_type)


def data_file_path(directory: str, filename: str) -> str:
    """Join a directory and filename for data access."""
    return str(Path(directory) / filename)


def workflow_temp_folder() -> str:
    """Return the temporary data folder used by the workflow."""
    return str(Path(ploemeur_obs.ploemeur_data_folder()) / "temp")


def workflow_temp_file_path(filename: str) -> str:
    """Return the full path for a workflow-generated temp data file."""
    return str(Path(workflow_temp_folder()) / filename)


def data_selection_filename(well: str, start: int, end: int) -> str:
    """Build the output filename for a selected data range."""
    return f"{well}_{start}_{int(end)}"


def results_dir_for_case(directory_results: str, well_date: str, lpm_type: str) -> str:
    """Return the results directory for a specific well/date/LPM case."""
    return str(
        result_subdirectory(result_subdirectory(directory_results, well_date), lpm_type)
    )
