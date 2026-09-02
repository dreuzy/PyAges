# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file prepares validated inputs and staging for a single-date workflow.

"""Build the shared runtime context used by every single-date workflow step.

Preparation loads the YAML settings and observation table, resolves missing
measurement errors according to policy, configures plotting, and locates model
and tracer resources. A private result stage is created only after these inputs
have passed validation.

The context carries the resolved configuration, observations, paths, display
session, and run handle so later steps do not reload them independently. A
companion function lists every scientific input that terminal provenance must
hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyages.calibration.problem import resolve_observation_errors
from pyages.concentrations import Concentrations
from pyages.config.models import LauncherParams
from pyages.config.paths import DIRECTORY_TRACER_DATA, configuration_root
from pyages.config.runtime import DisplayOptions
from pyages.workflows.runtime import ResultRun, begin_staged_result_run
from pyages.workflows.runtime.plotting import PlotSession
from pyages.workflows.single_date.config import load_params
from pyages.workflows.single_date.paths import dataset_results_directory


@dataclass(frozen=True)
class SingleDateContext:
    """All inputs and runtime services required by one workflow run."""

    config_path: Path
    root: Path
    params: LauncherParams
    result_run: ResultRun
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
    resolve_observation_errors(
        observations,
        tracer_data_directory=params.tracer_data_dir,
        missing_error_relative_fraction=params.missing_error_rel,
    )
    observations.display(display)
    return observations


def prepare_context(
    params_path: str | Path,
    *,
    force_inline: bool,
) -> SingleDateContext:
    """Resolve configuration, inputs, outputs, and plotting runtime."""
    config_path = Path(params_path).resolve()
    root = configuration_root(config_path)
    params = load_params(root, config_path)
    result_directory = Path(
        dataset_results_directory(
            params.dataset_name,
            use_default=params.results_use_default,
            directory=params.results_directory,
            study_name=params.results_study_name,
            create=False,
        )
    )
    live_display = _display_options(None, save=False, text=params.verbose)
    plots = PlotSession.start(force_inline=force_inline)
    try:
        observations = _load_observations(params, live_display)
        # Do not allocate a staged result tree until every scientific input
        # needed to start the workflow has been loaded successfully.
        result_run = begin_staged_result_run(result_directory)
    except BaseException:
        plots.close_all()
        raise
    output_directory = result_run.working_directory
    saved_display = _display_options(output_directory, save=True)
    return SingleDateContext(
        config_path=config_path,
        root=root,
        params=params,
        result_run=result_run,
        output_directory=output_directory,
        live_display=live_display,
        saved_display=saved_display,
        observations=observations,
        plots=plots,
    )


def scientific_input_paths(context: SingleDateContext) -> list[Path]:
    """Return every observation, model, and tracer resource used by the run."""
    tracer_root = context.params.tracer_data_dir or DIRECTORY_TRACER_DATA
    return [
        context.params.dataset_data_dir / context.params.dataset_name,
        context.params.directory_lpm / context.params.lpm_model_name,
        *(
            Path(tracer_root) / tracer
            for tracer in context.observations.observation_tracer_names()
        ),
    ]


__all__ = ["SingleDateContext", "prepare_context", "scientific_input_paths"]
