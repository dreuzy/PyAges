# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Installed single-date calibration workflow."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyages.calibration.methods.simplex import FORWARD_UNCERTAINTY, Simplex
from pyages.calibration.problem import CalibrationProblem
from pyages.calibration.utils.systematic_sampling import SystematicSampling
from pyages.concentrations import concentrations_time
from pyages.concentrations.concentrations import Concentrations
from pyages.config.paths import result_subdirectory
from pyages.config.runtime import DisplayOptions
from pyages.lpm.factory import build_lpm
from pyages.lpm.samples import LpmSampleTable
from pyages.workflows.plotting_runtime import PlotSession
from pyages.workflows.result_manifest import write_result_manifest
from pyages.workflows.single_date_config import LauncherParams, load_params
from pyages.workflows.single_date_paths import (
    configuration_root,
    dataset_results_directory,
)


@dataclass(frozen=True)
class WorkflowContext:
    """All inputs and runtime services required by one workflow run."""

    config_path: Path
    root: Path
    params: LauncherParams
    output_directory: Path
    live_display: DisplayOptions
    saved_display: DisplayOptions
    observations: Concentrations
    plots: PlotSession


def _display_options(
    directory: Path | None,
    *,
    save: bool,
    text: bool = False,
) -> DisplayOptions:
    options = DisplayOptions()
    options.text = text
    options.figure = True
    options.figure_save = save
    options.figure_close = save
    options.directory = directory
    return options


def _load_observations(
    params: LauncherParams,
    display: DisplayOptions,
) -> Concentrations:
    path = params.dataset_data_dir / params.dataset_name
    if params.verbose:
        print(f"Observation file: {path}")
    observations = Concentrations.from_file(path)
    observations.display(display)
    return observations


def _prepare_context(
    params_path: str | Path,
    *,
    force_inline: bool,
) -> WorkflowContext:
    config_path = Path(params_path).resolve()
    root = configuration_root(config_path)
    params = load_params(root, config_path)
    output_directory = Path(dataset_results_directory(params.dataset_name))
    output_directory.mkdir(parents=True, exist_ok=True)
    live_display = _display_options(None, save=False, text=params.verbose)
    saved_display = _display_options(output_directory, save=True)
    observations = _load_observations(params, live_display)
    observations.cv.to_csv(output_directory / "concentrations.txt", sep="\t")
    return WorkflowContext(
        config_path=config_path,
        root=root,
        params=params,
        output_directory=output_directory,
        live_display=live_display,
        saved_display=saved_display,
        observations=observations,
        plots=PlotSession.start(force_inline=force_inline),
    )


def _calibration_problem(
    context: WorkflowContext,
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


def _reachable_concentrations(context: WorkflowContext) -> pd.DataFrame | None:
    if not context.params.run_reachable_concentrations:
        return None
    display = copy.deepcopy(context.saved_display)
    display.directory = result_subdirectory(
        context.output_directory,
        "reachable_concentrations",
    )
    sampling = SystematicSampling(
        context.params.lpm_model_name,
        context.observations.names(),
        date=context.observations.cv["date"],
        sample_count=context.params.reachable_concentration_nmodels,
        display_options=display,
        lpm_directory=context.params.directory_lpm,
        tracer_data_directory=context.params.tracer_data_dir,
    )
    sampling.compute_concentrations()
    sampling.output()
    return sampling.concentrations_frame()


def _run_simplex(context: WorkflowContext) -> tuple[str, LpmSampleTable]:
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
    context: WorkflowContext,
) -> tuple[str, LpmSampleTable]:
    method = MetropolisHastings(
        config=MHConfig(
            nstep=context.params.mh_nstep,
            prior_option=context.params.mh_prior_option,
            likelihood=context.params.mh_likelihood,
            monitor=context.params.mh_monitor,
            display_traj=context.params.mh_display_traj,
            componentwise_source="model",
        )
    )
    problem = _calibration_problem(
        context,
        result_subdirectory(context.output_directory, method.method),
    )
    results = method.run(problem)
    method.write_calibrated_lpm(results)
    return method.method, results


def _run_calibrations(context: WorkflowContext) -> dict[str, LpmSampleTable]:
    results: dict[str, LpmSampleTable] = {}
    if context.params.run_calibration_simplex:
        method, distribution = _run_simplex(context)
        results[method] = distribution
    if context.params.run_calibration_metropolis_hastings:
        method, distribution = _run_metropolis_hastings(context)
        results[method] = distribution
    return results


def _case_label(params: LauncherParams) -> str:
    return params.dataset_label or Path(params.dataset_name).stem.replace("_", " ")


def _render_summary(
    context: WorkflowContext,
    reachable: pd.DataFrame | None,
    calibrated: dict[str, LpmSampleTable],
) -> None:
    if not calibrated:
        return
    from pyages.workflows.plots import (
        plot_parameter_summary,
        plot_single_date_model_space,
    )

    label = _case_label(context.params)
    if reachable is not None:
        figure = plot_single_date_model_space(
            context.observations,
            reachable_frame=reachable,
            posterior_results=calibrated,
            filename=context.output_directory / "01_data_model_space.png",
            title=f"{label}: observations, reachable space and calibrated models",
        )
        context.plots.show()
        context.plots.close(figure)
    parameter_names = next(iter(calibrated.values())).get_param_names()
    figure = plot_parameter_summary(
        calibrated,
        param_names=parameter_names,
        filename=context.output_directory / "02_parameter_summary.png",
        title=f"{label}: parameter distributions",
    )
    context.plots.show()
    context.plots.close(figure)


def _run_objective_analysis(
    context: WorkflowContext,
    calibrated: dict[str, LpmSampleTable],
) -> None:
    if not context.params.run_objective_function:
        return
    from pyages.workflows.plots import plot_objective_summary

    sampling = SystematicSampling(
        context.params.lpm_model_name,
        context.observations.names(),
        date=context.observations.cv["date"],
        observations=context.observations,
        sample_count=context.params.objective_function_nmodels,
        display_options=context.live_display,
        explore_objective=True,
        explore_reachable=False,
        lpm_directory=context.params.directory_lpm,
        tracer_data_directory=context.params.tracer_data_dir,
    )
    sampling.compute_concentrations()
    sampling.objective_function_build()
    objective = sampling.objective_function_frame()
    objective.to_csv(
        context.output_directory / "objective_function_grid.txt",
        sep="\t",
        index=False,
    )
    figure = plot_objective_summary(
        objective_frame=objective,
        posterior_results=calibrated,
        param_names=sampling.parameter_names(),
        filename=context.output_directory / "03_objective_summary.png",
        title=f"{_case_label(context.params)}: objective landscape and parameters",
    )
    context.plots.show()
    context.plots.close(figure)


def _write_concentration_outputs(context: WorkflowContext) -> None:
    model = build_lpm(
        context.params.lpm_model_name,
        directory_lpm=context.params.directory_lpm,
    )
    concentrations_time.display_concentration_times(
        [context.output_directory],
        model,
        context.saved_display,
    )


def run_single_date(params_path: str | Path, force_inline: bool = False) -> Path:
    """Run every enabled step from a single-date YAML configuration."""
    if params_path is None:
        raise ValueError("params_path is required for the launcher")
    context = _prepare_context(params_path, force_inline=force_inline)
    reachable = _reachable_concentrations(context)
    calibrated = _run_calibrations(context)
    _render_summary(context, reachable, calibrated)
    _run_objective_analysis(context, calibrated)
    _write_concentration_outputs(context)
    context.plots.finish()
    write_result_manifest(
        context.output_directory,
        workflow="single_date",
        config_path=context.config_path,
        input_paths=[context.params.dataset_data_dir / context.params.dataset_name],
        details={
            "dataset": context.params.dataset_name,
            "lpm": context.params.lpm_model_name,
            "calibrations": sorted(calibrated),
        },
    )
    return context.output_directory


__all__ = ["run_single_date"]
