# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file calibrates one LPM for one case of a temporal workflow.

"""Build and run the MH calibration requested for one temporal model and case.

Validated workflow settings are translated into the single- or multi-chain MH
configuration used by the calibration package. The selected LPM is fitted to all
dated tracer observations in the current case, and its sample tables are written
beneath that case's staged result directory.

When enabled, the same result is passed to temporal-fit, parameter-distribution,
and concentration-diagnostic plotting functions. Run-level status, iteration
over cases, provenance, and publication remain the responsibility of the runner.
"""

from __future__ import annotations

from pathlib import Path

from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.config.models import TemporalCalibrationCfg, TemporalReportingCfg
from pyages.config.runtime import DisplayOptions
from pyages.lpm.plotting.sample_diagnostics import plot_concentration_diagnostics
from pyages.reporting.chronicles import export_calibrated_chronicles
from pyages.reporting.plots import plot_parameter_summary
from pyages.workflows.runtime.mh import run_mh_calibration


def _prepare_display(
    output_directory: Path,
    figures_cfg: TemporalReportingCfg,
) -> DisplayOptions:
    """Create display options for a single calibration run."""
    display = DisplayOptions()
    display.text = False
    display.figure = bool(figures_cfg.temporal or figures_cfg.distributions)
    display.figure_save = True
    display.figure_close = True
    display.directory = str(output_directory)
    return display


def run_model_calibration(
    observations: Concentrations,
    lpm_type: str,
    output_directory: Path,
    lpm_directory: Path,
    calibration_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalReportingCfg,
) -> None:
    """Calibrate one LPM against one temporal observation case and write outputs.

    ``calibration_cfg.metropolis_hastings`` is the chain configuration shared by
    all chain counts. Its ``chains`` value selects one or several production chains
    without changing engine or configuration shape. Execution, persistence,
    and any applicable qualification are delegated to ``run_mh_calibration``.

    The calibrated sample table is then used for the figures enabled by
    ``figures_cfg``. ``posterior_draw_count`` controls how many realizations enter temporal
    summaries; a non-positive value derives a bounded count from the requested
    MH length. All output is written below ``output_directory``. The function
    returns nothing and propagates configuration, calibration, convergence, or
    rendering failures to the workflow runner.
    """
    display = _prepare_display(output_directory, figures_cfg)
    mh_config = calibration_cfg.metropolis_hastings
    posterior_draw_count = int(calibration_cfg.posterior_draw_count)
    if posterior_draw_count <= 0:
        posterior_draw_count = max(min(int(mh_config.nsteps / 50), 5000), 10)

    # Loading tracer histories and building their adaptive grids is independent
    # of the chain. Prepare that scientific target once, then give every MH
    # stage its own mutable LPM, convolution diagnostics, and display directory.
    problem_template = CalibrationProblem(
        observations,
        lpm_type,
        display_options=display,
        lpm_directory=lpm_directory,
        sample_count=int(calibration_cfg.exploration_resolution),
        explore_reachable=False,
    ).prepare()

    def problem_builder(directory: Path) -> CalibrationProblem:
        return problem_template.clone_prepared(
            display_options=_prepare_display(directory, figures_cfg)
        )

    lpm_results = run_mh_calibration(
        mh_config,
        output_directory,
        problem_builder,
    )
    method_name = "Metropolis_Hastings"

    if figures_cfg.temporal:
        export_calibrated_chronicles(
            observations,
            lpm_results,
            method_name,
            display,
            posterior_draw_count=posterior_draw_count,
        )

    if figures_cfg.distributions:
        figure = plot_parameter_summary(
            {method_name: lpm_results},
            param_names=lpm_results.get_param_names(),
            filename=output_directory / "parameter_summary.png",
            title=f"{lpm_type}: calibrated parameter distributions",
        )
        import matplotlib.pyplot as plt

        plt.close(figure)
        if figures_cfg.concentrations_2d:
            plot_concentration_diagnostics(
                lpm_results,
                self_method=method_name,
                concentrations_reference=observations,
                directory=display.directory,
            )


__all__ = ["run_model_calibration"]
