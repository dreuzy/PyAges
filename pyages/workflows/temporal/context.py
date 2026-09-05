# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file prepares validated inputs and staging for a temporal workflow.

"""Build the shared context for a temporal workflow from its YAML configuration.

Preparation resolves observation and data directories, validates the requested
LPM names, loads dated concentrations, and fills missing measurement errors by
the configured policy. Plotting is configured and a private result stage is
created only after the scientific inputs are usable.

The resulting context is reused across temporal cases and model calibrations.
It also identifies every dataset, model definition, and tracer resource whose
contents must be included in terminal provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pyages.calibration.problem import resolve_observation_errors
from pyages.concentrations import Concentrations
from pyages.concentrations.schema import ERROR_COLUMN
from pyages.config.loading import resolve_from, validate_yaml_model
from pyages.config.models import (
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
)
from pyages.config.paths import (
    DIRECTORY_LPM_DATA,
    DIRECTORY_TRACER_DATA,
    ROOT_DIRECTORY_RESULTS,
    configuration_root,
    result_subdirectory,
    validate_path_component,
)
from pyages.workflows.runtime import ResultRun, begin_staged_result_run

DEFAULT_LPMS = ["exp_shifted", "ig", "ig_shifted"]


@dataclass(frozen=True)
class TemporalContext:
    """Resolved configuration and inputs for one temporal workflow."""

    config_path: Path
    configuration_directory: Path
    params: TemporalParams
    dataset_path: Path
    mode: str
    models: list[str]
    lpm_directory: Path
    observations: Concentrations
    result_run: ResultRun
    output_directory: Path


def _load_params_validated(path: Path) -> TemporalParams:
    """Load and validate a temporal workflow configuration."""
    return cast(
        TemporalParams,
        validate_yaml_model(
            path,
            TemporalParams,
            label="temporal workflow configuration",
        ),
    )


def _results_root(
    results_cfg: TemporalResultsCfg,
    configuration_directory: Path,
) -> Path:
    """Resolve and, when needed, create the configured results root."""
    if results_cfg.use_default:
        return ROOT_DIRECTORY_RESULTS
    directory = results_cfg.directory
    if not directory:
        raise ValueError("results.directory must be set when use_default is false.")
    results_path = resolve_from(configuration_directory, directory)
    results_path.mkdir(parents=True, exist_ok=True)
    return results_path


def _resolve_lpms(
    lpm_cfg: TemporalLpmModelsCfg,
    configuration_directory: Path,
) -> tuple[list[str], Path]:
    """Resolve the requested models and their parameter directory."""
    models = DEFAULT_LPMS.copy() if lpm_cfg.list is None else list(lpm_cfg.list)
    if not models:
        raise ValueError("lpm_models.list must be a non-empty list.")
    models = [
        validate_path_component(model, label="lpm_models.list item") for model in models
    ]
    directory = resolve_from(
        configuration_directory,
        lpm_cfg.directory or DIRECTORY_LPM_DATA,
    )
    if not directory.is_dir():
        raise ValueError(f"lpm_models.directory is not a directory: {directory}")
    return models, directory


def _load_concentrations(
    dataset_path: Path,
    error_rel: float | None,
    missing_error_rel: float = 0.01,
) -> Concentrations:
    """Load observations and fill missing relative errors when requested."""
    concentrations = Concentrations.from_file(dataset_path)
    if error_rel is not None and concentrations.frame[ERROR_COLUMN].min() == 0:
        concentrations.set_relative_errors(float(error_rel))
    resolve_observation_errors(
        concentrations,
        missing_error_relative_fraction=missing_error_rel,
    )
    return concentrations


def prepare_context(params_path: str | Path) -> TemporalContext:
    """Resolve a temporal configuration into immutable runtime context."""
    config_path = Path(params_path).resolve()
    configuration_directory = configuration_root(config_path)
    params = _load_params_validated(config_path)
    dataset_path = resolve_from(configuration_directory, params.dataset.file)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    models, lpm_directory = _resolve_lpms(
        params.lpm_models,
        configuration_directory,
    )
    observations = _load_concentrations(
        dataset_path,
        params.dataset.error_rel,
        params.dataset.missing_error_rel,
    )
    # Allocate the staging tree only after all scientific inputs required to
    # start the workflow have passed validation and loading.
    results_root = _results_root(params.results, configuration_directory)
    result_parent = result_subdirectory(
        result_subdirectory(results_root, params.results.study_name),
        dataset_path.stem,
    )
    # Keep the public leaf absent until atomic promotion. Creating an empty leaf
    # here makes its disappearance observable as a false concurrent mutation.
    result_directory = result_parent / params.workflow.mode
    result_run = begin_staged_result_run(result_directory)
    output_directory = result_run.working_directory
    return TemporalContext(
        config_path=config_path,
        configuration_directory=configuration_directory,
        params=params,
        dataset_path=dataset_path,
        mode=params.workflow.mode,
        models=models,
        lpm_directory=lpm_directory,
        observations=observations,
        result_run=result_run,
        output_directory=output_directory,
    )


def scientific_input_paths(context: TemporalContext) -> list[Path]:
    """Return every observation, model, and tracer resource used by the run."""
    return [
        context.dataset_path,
        *(context.lpm_directory / model for model in context.models),
        *(
            DIRECTORY_TRACER_DATA / tracer
            for tracer in context.observations.observation_tracer_names()
        ),
    ]


__all__ = ["TemporalContext", "prepare_context", "scientific_input_paths"]
