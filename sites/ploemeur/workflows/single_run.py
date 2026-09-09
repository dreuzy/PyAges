# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Execute and report one prepared Ploemeur calibration case."""

from __future__ import annotations

import copy
from pathlib import Path

from pyages.calibration.methods.mh.prior import Prior
from pyages.calibration.outputs import posterior_directory
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.concentrations.schema import ERROR_COLUMN
from pyages.config.paths import result_subdirectory
from pyages.config.runtime import DisplayOptions
from pyages.data_io.lpm_distribution import write_histograms
from pyages.lpm.plotting.sample_diagnostics import plot_prior_comparison
from pyages.lpm.samples import LpmSampleTable
from pyages.reporting.chronicles import export_calibrated_chronicles
from pyages.workflows.runtime.mh import (
    build_mh_config,
    build_mh_run_config,
    execute_mh_run,
)
from sites.ploemeur.config.models import PloemeurCalibrationConfig
from sites.ploemeur.workflows.job_builder import validate_time_span_and_prior_mode
from sites.ploemeur.workflows.path_helpers import (
    calibrated_prior_name,
    data_file_path,
    results_dir_for_case,
    workflow_temp_folder,
)


def _load_concentrations(
    file_path: str | Path,
    error_concentrations: float,
    display: DisplayOptions,
    output_directory: str | Path,
) -> Concentrations:
    """Load, normalize, display, and persist one observation table."""
    observations = Concentrations.from_file(file_path)
    if observations.frame[ERROR_COLUMN].min() == 0:
        observations.set_relative_errors(error_concentrations)
    observations.display(display)
    observations.frame.to_csv(
        data_file_path(output_directory, "concentrations.txt"),
        sep="\t",
        index=False,
    )
    return observations


class PloemeurSingleRun:
    """Run one well, date range, LPM, and prior mode through managed MH."""

    def __init__(
        self,
        directory_results: str | Path,
        well_date: str,
        error_concentrations: float,
        lpm_type: str,
        calibration_config: PloemeurCalibrationConfig,
        prior: bool,
        likelihood: bool,
        directory_lpm: str | Path,
        time_span_and_prior_mode: str,
        observation_directory: str | Path | None = None,
        prior_file: str = "",
    ) -> None:
        """Prepare paths, display policy, and exact MH configurations."""
        validate_time_span_and_prior_mode(time_span_and_prior_mode)
        self.time_span_and_prior_mode = time_span_and_prior_mode
        source_directory = observation_directory or workflow_temp_folder()
        self.file_ploemeur = data_file_path(source_directory, well_date)
        self.file_stem = Path(self.file_ploemeur).name
        self.error_concentrations = error_concentrations
        self.lpm_type = lpm_type
        self.directory_lpm = directory_lpm

        mh_config = calibration_config.metropolis_hastings
        self.run_config = build_mh_run_config(mh_config)
        if self.run_config.seed is None:  # pragma: no cover - realized by config.
            raise AssertionError("managed Ploemeur MH run has no realized seed")
        self.chain_config = build_mh_config(
            mh_config,
            seed=self.run_config.seed,
            prior_option=prior,
            likelihood=likelihood,
            prior_type="empirical",
            prior_file=prior_file,
        )
        self.exploration_resolution = calibration_config.exploration_resolution
        self.posterior_draw_count = calibration_config.posterior_draw_count

        self.display = DisplayOptions()
        self.display.text = False
        self.display.figure = True
        self.display.figure_close = True
        self.display.figure_save = True
        self.output_directory = results_dir_for_case(
            directory_results, self.file_stem, lpm_type
        )
        self.display.directory = self.output_directory

    def concentration_preparation(self) -> Concentrations:
        """Load the case observations and write their normalized table."""
        return _load_concentrations(
            file_path=self.file_ploemeur,
            error_concentrations=self.error_concentrations,
            display=self.display,
            output_directory=self.output_directory,
        )

    def calibrate(self, observations: Concentrations) -> LpmSampleTable:
        """Run managed MH once, then create the Ploemeur-specific products."""
        method_directory = Path(
            result_subdirectory(self.output_directory, "Metropolis_Hastings")
        )
        method_display = copy.deepcopy(self.display)
        method_display.directory = method_directory

        template = CalibrationProblem(
            observations,
            self.lpm_type,
            display_options=method_display,
            lpm_directory=self.directory_lpm,
            sample_count=self.exploration_resolution,
            explore_reachable=False,
        ).prepare()

        def problem_builder(directory: Path) -> CalibrationProblem:
            stage_display = copy.deepcopy(method_display)
            stage_display.directory = directory
            return template.clone_prepared(display_options=stage_display)

        lpm_results = execute_mh_run(
            self.chain_config,
            self.run_config,
            method_directory,
            problem_builder,
        )

        prior_name = calibrated_prior_name(
            self.file_stem, self.error_concentrations, self.lpm_type
        )
        prior_output = posterior_directory(
            method_directory,
            parent_levels=5,
            subdirectory=self.time_span_and_prior_mode,
        )
        write_histograms(lpm_results, prior_output / f"{prior_name}.txt")
        template.analyze(lpm_results)

        export_calibrated_chronicles(
            observations,
            lpm_results,
            "Metropolis_Hastings",
            self.display,
            posterior_draw_count=self.posterior_draw_count,
        )
        if self.chain_config.prior_option:
            if template.lpm is None:  # pragma: no cover - guarded by prepare().
                raise AssertionError("prepared Ploemeur problem has no LPM")
            empirical_prior = Prior(
                option=True,
                typ="empirical",
                prior_file=self.chain_config.prior_file,
            )
            empirical_prior.load(template.lpm)
            plot_prior_comparison(
                lpm_results,
                directory=method_directory,
                prior=empirical_prior,
            )

        return lpm_results

    def perform(self) -> None:
        """Run preparation, calibration, and reporting for this case."""
        self.calibrate(self.concentration_preparation())


__all__ = ["PloemeurSingleRun"]
