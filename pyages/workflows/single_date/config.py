# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file reads a single-date YAML mapping relative to its configuration root
# and validates it with the launcher schema. It returns resolved dataset, model,
# result-path, and calibration settings, with clear errors for invalid input.

"""Configuration adapter for the single-date workflow."""

import warnings
from pathlib import Path

from pydantic import ValidationError

from pyages.config.loading import load_yaml_mapping
from pyages.config.migration import normalize_configuration_payload
from pyages.config.models import LauncherConfig, LauncherParams


def load_config_payload(root_dir: Path, data: dict) -> LauncherConfig:
    """Validate a single-date mapping and preserve its nested YAML structure."""
    try:
        runtime_data = normalize_configuration_payload(
            data,
            expected_kind="single_date",
        )
        return LauncherConfig.model_validate(
            runtime_data,
            context={"root_dir": root_dir},
        )
    except ValidationError as exc:
        raise ValueError(f"Invalid single-date workflow configuration:\n{exc}") from exc


def load_config(root_dir: Path, params_path: Path) -> LauncherConfig:
    """Load the canonical nested configuration used by the workflow."""
    return load_config_payload(root_dir, load_yaml_mapping(params_path))


def _flatten_config(config: LauncherConfig) -> LauncherParams:
    """Build the deprecated 1.x record from the canonical nested model."""
    return LauncherParams(
        dataset_name=config.dataset.name,
        dataset_label=config.dataset.label,
        dataset_year=config.dataset.year,
        dataset_data_dir=config.dataset.data_dir,
        verbose=config.dataset.verbose,
        missing_error_rel=config.dataset.missing_error_rel,
        lpm_model_name=config.lpm.model_name,
        directory_lpm=config.lpm.data_directory,
        tracer_data_dir=config.tracers.data_directory,
        run_reachable_concentrations=config.run.reachable_concentrations,
        run_objective_function=config.run.objective_function,
        run_calibration_metropolis_hastings=(
            config.run.calibration_metropolis_hastings
        ),
        run_calibration_simplex=config.run.calibration_simplex,
        reachable_concentration_nmodels=config.reachable_concentrations.nmodels,
        objective_function_nmodels=config.objective_function.nmodels,
        mh_nstep=config.calibration_metropolis_hastings.nstep,
        mh_prior_option=config.calibration_metropolis_hastings.prior_option,
        mh_likelihood=config.calibration_metropolis_hastings.likelihood,
        mh_monitor=config.calibration_metropolis_hastings.monitor,
        mh_display_traj=config.calibration_metropolis_hastings.display_traj,
        simplex_init_multiples_n=config.calibration_simplex.init_multiples_n,
        simplex_fuq_n=config.calibration_simplex.fuq_n,
    )


def load_params_payload(root_dir: Path, data: dict) -> LauncherParams:
    """Return the deprecated flattened 1.x configuration view."""
    warnings.warn(
        "load_params_payload() is deprecated; use load_config_payload() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return _flatten_config(load_config_payload(root_dir, data))


def load_params(root_dir: Path, params_path: Path) -> LauncherParams:
    """Load the deprecated flattened 1.x configuration view."""
    warnings.warn(
        "load_params() is deprecated; use load_config() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return _flatten_config(load_config(root_dir, params_path))


__all__ = ["load_config", "load_config_payload", "load_params", "load_params_payload"]
