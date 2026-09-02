# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file runs reachability analysis and calibration for a single-date case.

"""Apply enabled calibration methods to an already prepared single-date context.

Reachability sampling evaluates the configured LPM across parameter space before
fitting, showing which tracer combinations the model can produce. Calibration
then builds one shared scientific problem and dispatches the enabled Simplex or
Metropolis--Hastings implementations.

Each method writes only beneath its staged result directory, while the returned
mapping keeps its calibrated sample table available to later reporting steps.
This module does not publish the stage or write the terminal run manifest.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from pyages.calibration.exploration.systematic import SystematicSampling
from pyages.calibration.methods.mh import (
    MetropolisHastings,
    MHConfig,
)
from pyages.calibration.methods.simplex import FORWARD_UNCERTAINTY, Simplex
from pyages.calibration.problem import CalibrationProblem
from pyages.config.paths import result_subdirectory
from pyages.data_io.mh_results import (
    clear_mh_ensemble_artifacts,
)
from pyages.lpm.samples import LpmSampleTable
from pyages.workflows.runtime.mh import run_mh_ensemble
from pyages.workflows.single_date.context import SingleDateContext


def _calibration_problem(
    context: SingleDateContext,
    output_directory: Path,
) -> CalibrationProblem:
    display = copy.deepcopy(context.saved_display)
    display.directory = output_directory
    return CalibrationProblem(
        context.observations,
        context.params.lpm_model_name,
        display_options=display,
        lpm_directory=context.params.directory_lpm,
        tracer_data_directory=context.params.tracer_data_dir,
    ).prepare()


def reachable_concentrations(context: SingleDateContext) -> pd.DataFrame | None:
    """Compute the reachable model space when enabled."""
    if not context.params.run_reachable_concentrations:
        return None
    display = copy.deepcopy(context.saved_display)
    display.directory = result_subdirectory(
        context.output_directory,
        "reachable_concentrations",
    )
    sampling = SystematicSampling(
        context.params.lpm_model_name,
        context.observations.observation_tracer_names(),
        date=context.observations.frame["date"],
        sample_count=context.params.reachable_concentration_nmodels,
        display_options=display,
        lpm_directory=context.params.directory_lpm,
        tracer_data_directory=context.params.tracer_data_dir,
    )
    sampling.compute_concentrations()
    sampling.output()
    return sampling.concentrations_frame()


def _run_simplex(context: SingleDateContext) -> tuple[str, LpmSampleTable]:
    method = Simplex(
        FORWARD_UNCERTAINTY,
        init_multiples_n=context.params.simplex_init_multiples_n,
        fuq_n=context.params.simplex_fuq_n,
    )
    problem = _calibration_problem(
        context,
        result_subdirectory(context.output_directory, method.method),
    )
    results = method.run(problem)
    method.write_calibrated_lpm(results)
    return method.method, results


def _run_metropolis_hastings(
    context: SingleDateContext,
) -> tuple[str, LpmSampleTable]:
    chain_config = MHConfig(
        nstep=context.params.mh_nstep,
        burn_in=context.params.mh_burn_in,
        nskip=context.params.mh_nskip,
        prior_option=context.params.mh_prior_option,
        likelihood=context.params.mh_likelihood,
        monitor=context.params.mh_monitor,
        display_traj=context.params.mh_display_traj,
        componentwise_source="model",
        seed=context.params.mh_seed,
    )
    output_directory = result_subdirectory(
        context.output_directory, "Metropolis_Hastings"
    )
    multichain_cfg = context.params.mh_multichain
    if multichain_cfg is None or not multichain_cfg.enabled:
        clear_mh_ensemble_artifacts(output_directory)
        method = MetropolisHastings(config=chain_config)
        problem = _calibration_problem(context, output_directory)
        results = method.run(problem)
        method.write_calibrated_lpm(results)
        return method.method, results

    pooled = run_mh_ensemble(
        chain_config,
        multichain_cfg,
        output_directory,
        lambda directory: _calibration_problem(context, directory),
    )
    return "Metropolis_Hastings", pooled


def run_calibrations(context: SingleDateContext) -> dict[str, LpmSampleTable]:
    """Run each independently enabled calibration strategy."""
    results: dict[str, LpmSampleTable] = {}
    if context.params.run_calibration_simplex:
        method, distribution = _run_simplex(context)
        results[method] = distribution
    if context.params.run_calibration_metropolis_hastings:
        method, distribution = _run_metropolis_hastings(context)
        results[method] = distribution
    return results


__all__ = ["reachable_concentrations", "run_calibrations"]
