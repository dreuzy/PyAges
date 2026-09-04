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
from pyages.config.models import TemporalCalibrationCfg, TemporalFiguresCfg
from pyages.config.runtime import DisplayOptions
from pyages.lpm.plotting.sample_diagnostics import plot_concentration_diagnostics
from pyages.reporting.chronicles import export_calibrated_chronicles
from pyages.reporting.plots import plot_parameter_summary
from pyages.workflows.runtime.mh import build_mh_config, run_mh_calibration


def _prepare_display(
    output_directory: Path,
    figures_cfg: TemporalFiguresCfg,
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
    figures_cfg: TemporalFiguresCfg,
) -> None:
    """Calibrate one LPM against one temporal observation case and write outputs.

    ``calibration_cfg`` is converted into the chain configuration shared by both
    execution modes. A disabled or absent ensemble configuration runs one
    ``MetropolisHastings`` sampler after clearing stale multi-chain artifacts;
    an enabled ensemble delegates isolated chain execution, diagnostics, and
    qualified pooling to ``run_mh_ensemble``.

    The calibrated sample table is then used for the figures enabled by
    ``figures_cfg``. ``lpm_number`` controls how many realizations enter temporal
    summaries; a non-positive value derives a bounded count from the requested
    MH length. All output is written below ``output_directory``. The function
    returns nothing and propagates configuration, calibration, convergence, or
    rendering failures to the workflow runner.
    """
    display = _prepare_display(output_directory, figures_cfg)
    lpm_number = int(calibration_cfg.lpm_number)
    if lpm_number <= 0:
        lpm_number = max(min(int(calibration_cfg.mh_nsteps / 50), 5000), 10)

    mh_config = build_mh_config(calibration_cfg)

    def problem_builder(directory: Path) -> CalibrationProblem:
        return CalibrationProblem(
            observations,
            lpm_type,
            display_options=_prepare_display(directory, figures_cfg),
            lpm_directory=lpm_directory,
            sample_count=int(calibration_cfg.explo_res),
            explore_reachable=False,
        ).prepare()

    lpm_results = run_mh_calibration(
        mh_config,
        calibration_cfg.multichain,
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
            lpm_number=lpm_number,
        )

    if figures_cfg.distributions:
        figure = plot_parameter_summary(
            {method_name: lpm_results},
            param_names=lpm_results.get_param_names(),
            filename=Path(display.directory) / "parameter_summary.png",
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
