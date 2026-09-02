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

import secrets
from pathlib import Path

from pyages.calibration.methods.mh import (
    MetropolisHastings,
    MHConfig,
)
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.config.models import TemporalCalibrationCfg, TemporalFiguresCfg
from pyages.config.runtime import DisplayOptions
from pyages.data_io.mh_results import (
    clear_mh_ensemble_artifacts,
)
from pyages.lpm.plotting.sample_diagnostics import plot_concentration_diagnostics
from pyages.reporting.chronicles import export_calibrated_chronicles
from pyages.reporting.plots import plot_parameter_summary
from pyages.workflows.runtime.mh import run_mh_ensemble


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


def build_mh_config(calibration_cfg: TemporalCalibrationCfg) -> MHConfig:
    """Build a Metropolis-Hastings configuration from validated settings."""
    multichain_enabled = (
        calibration_cfg.multichain is not None and calibration_cfg.multichain.enabled
    )
    if multichain_enabled:
        # The ensemble replaces this placeholder with one independent seed per
        # production chain; no unrelated random draw should enter provenance.
        seed_value = 0
    else:
        seed_value = (
            calibration_cfg.seed
            if calibration_cfg.seed_enabled
            else secrets.randbits(63)
        )
    if seed_value is None:
        raise ValueError("calibration.seed is required when seed_enabled is true")
    return MHConfig(
        nstep=int(calibration_cfg.mh_nsteps),
        burn_in=float(calibration_cfg.burn_in),
        nskip=int(calibration_cfg.nskip),
        prior_option=True,
        prior_type="parametric",
        likelihood=True,
        monitor=False,
        display_traj=False,
        display_text=False,
        componentwise_source="model",
        seed=seed_value,
    )


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
    multichain_cfg = calibration_cfg.multichain
    # The execution branches produce the same sample-table contract, allowing
    # all optional report generation below to remain mode-independent.
    if multichain_cfg is None or not multichain_cfg.enabled:
        clear_mh_ensemble_artifacts(output_directory)
        problem = CalibrationProblem(
            observations,
            lpm_type,
            display_options=display,
            lpm_directory=lpm_directory,
            sample_count=int(calibration_cfg.explo_res),
            explore_reachable=False,
        ).prepare()
        calibration = MetropolisHastings(config=mh_config)
        lpm_results = calibration.run(problem)
        calibration.write_calibrated_lpm(lpm_results)
        method_name = calibration.method
    else:

        def problem_builder(directory: Path) -> CalibrationProblem:
            stage_display = _prepare_display(directory, figures_cfg)
            return CalibrationProblem(
                observations,
                lpm_type,
                display_options=stage_display,
                lpm_directory=lpm_directory,
                sample_count=int(calibration_cfg.explo_res),
                explore_reachable=False,
            ).prepare()

        lpm_results = run_mh_ensemble(
            mh_config,
            multichain_cfg,
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


__all__ = ["build_mh_config", "run_model_calibration"]
