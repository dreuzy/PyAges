"""Compatibility imports for the pre-0.1 calibration API.

New code should import :class:`pyage.calibration.problem.CalibrationProblem`
and the helpers from :mod:`pyage.calibration.outputs`.
"""

from pyage.calibration.outputs import posterior_directory, posterior_file_stem
from pyage.calibration.problem import CalibrationProblem


class CalibrationCore(CalibrationProblem):
    """Compatibility adapter for historical constructor keyword names."""

    def __init__(
        self,
        cdata,
        LPM_type,
        display_options=None,
        directory_lpm=None,
        tracer_data_dir=None,
        nmodels=1000,
        objfunc=True,
        reachconc=True,
    ):
        kwargs = {
            "display_options": display_options,
            "tracer_data_directory": tracer_data_dir,
            "sample_count": nmodels,
            "explore_objective": objfunc,
            "explore_reachable": reachconc,
        }
        if directory_lpm is not None:
            kwargs["lpm_directory"] = directory_lpm
        super().__init__(cdata, LPM_type, **kwargs)


def folder_prior_posterior(file, stageup=-5, folder_prior=""):
    """Compatibility wrapper around :func:`posterior_directory`."""
    return posterior_directory(
        file,
        parent_levels=abs(stageup),
        subdirectory=folder_prior,
    )


def file_prior_posterior(file_ploemeur, error_concentrations, lpm_type):
    """Compatibility wrapper around :func:`posterior_file_stem`."""
    return posterior_file_stem(file_ploemeur, error_concentrations, lpm_type)


__all__ = [
    "CalibrationCore",
    "CalibrationProblem",
    "file_prior_posterior",
    "folder_prior_posterior",
]
