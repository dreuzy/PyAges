# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file reads a single-date YAML mapping relative to its configuration root
# and validates it with the launcher schema. It returns resolved dataset, model,
# result-path, and calibration settings, with clear errors for invalid input.

"""Configuration adapter for the single-date workflow."""

from pathlib import Path

from pydantic import ValidationError

from pyages.config.loading import load_yaml_mapping
from pyages.config.models import LauncherConfig, LauncherParams


def load_params_payload(root_dir: Path, data: dict) -> LauncherParams:
    """Validate one launcher-only mapping and resolve its relative paths."""
    try:
        cfg = LauncherConfig.model_validate(data, context={"root_dir": root_dir})
    except ValidationError as exc:
        raise ValueError(f"Invalid single-date workflow configuration:\n{exc}") from exc

    return LauncherParams(
        dataset_name=cfg.dataset.name,
        dataset_label=cfg.dataset.label,
        dataset_year=cfg.dataset.year,
        dataset_data_dir=cfg.dataset.data_dir,
        verbose=cfg.dataset.verbose,
        missing_error_rel=cfg.dataset.missing_error_rel,
        lpm_model_name=cfg.lpm.model_name,
        directory_lpm=cfg.lpm.data_directory,
        tracer_data_dir=cfg.tracers.data_directory,
        run_reachable_concentrations=cfg.run.reachable_concentrations,
        run_objective_function=cfg.run.objective_function,
        run_calibration_metropolis_hastings=cfg.run.calibration_metropolis_hastings,
        run_calibration_simplex=cfg.run.calibration_simplex,
        reachable_concentration_nmodels=cfg.reachable_concentrations.nmodels,
        objective_function_nmodels=cfg.objective_function.nmodels,
        mh_nstep=cfg.calibration_metropolis_hastings.nstep,
        mh_burn_in=cfg.calibration_metropolis_hastings.burn_in,
        mh_nskip=cfg.calibration_metropolis_hastings.nskip,
        mh_seed=cfg.calibration_metropolis_hastings.seed,
        mh_prior_option=cfg.calibration_metropolis_hastings.prior_option,
        mh_likelihood=cfg.calibration_metropolis_hastings.likelihood,
        mh_monitor=cfg.calibration_metropolis_hastings.monitor,
        mh_display_traj=cfg.calibration_metropolis_hastings.display_traj,
        mh_multichain=cfg.calibration_metropolis_hastings.multichain,
        simplex_init_multiples_n=cfg.calibration_simplex.init_multiples_n,
        simplex_fuq_n=cfg.calibration_simplex.fuq_n,
        results_use_default=cfg.results.use_default,
        results_directory=cfg.results.directory,
        results_study_name=cfg.results.study_name,
    )


def load_params(root_dir: Path, params_path: Path) -> LauncherParams:
    """Load and validate a launcher-only YAML configuration."""
    return load_params_payload(root_dir, load_yaml_mapping(params_path))


__all__ = ["load_params", "load_params_payload"]
