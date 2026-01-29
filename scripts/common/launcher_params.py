# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Parameter loader for launcher workflows (Pydantic-validated).
"""

from pathlib import Path
import yaml

from pydantic import ValidationError

from pyage.config.models import LauncherConfig, LauncherParams



def load_params(root_dir: Path, params_path: Path) -> LauncherParams:
    """
    Purpose
    -------
    Load YAML parameters and resolve relative paths.

    Parameters
    ----------
    root_dir : Path
        Repository root used to resolve relative paths in the YAML.
    params_path : Path
        YAML file containing the example parameters.

    Returns
    -------
    LauncherParams
        Typed parameters used by the workflow.
    """
    data = yaml.safe_load(params_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid params structure in {params_path}")

    try:
        cfg = LauncherConfig.model_validate(data, context={"root_dir": root_dir})
    except ValidationError as exc:
        raise ValueError(f"Invalid launcher config:\n{exc}") from exc

    return LauncherParams(
        dataset_name=cfg.dataset.name,
        dataset_year=cfg.dataset.year,
        dataset_data_dir=cfg.dataset.data_dir,
        verbose=cfg.dataset.verbose,
        lpm_model_name=cfg.lpm.model_name,
        directory_lpm=cfg.lpm.data_directory,
        run_reachable_concentrations=cfg.run.reachable_concentrations,
        run_objective_function=cfg.run.objective_function,
        run_calibration_metropolis_hastings=cfg.run.calibration_metropolis_hastings,
        run_calibration_simplex=cfg.run.calibration_simplex,
        reachable_concentration_nmodels=cfg.reachable_concentrations.nmodels,
        objective_function_nmodels=cfg.objective_function.nmodels,
        mh_nstep=cfg.calibration_metropolis_hastings.nstep,
        mh_prior_option=cfg.calibration_metropolis_hastings.prior_option,
        mh_likelihood=cfg.calibration_metropolis_hastings.likelihood,
        mh_monitor=cfg.calibration_metropolis_hastings.monitor,
        mh_display_traj=cfg.calibration_metropolis_hastings.display_traj,
        simplex_init_multiples_n=cfg.calibration_simplex.init_multiples_n,
        simplex_fuq_n=cfg.calibration_simplex.fuq_n,
    )
