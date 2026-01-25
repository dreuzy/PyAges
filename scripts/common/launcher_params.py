# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 20:35:54 2021

@author: Jean-Raynald de Dreuzy

Parameter loader for launcher workflows.
"""

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class LauncherParams:
    """Typed parameters for the launcher workflow."""

    dataset_name: str
    dataset_year: int
    dataset_data_dir: Path
    verbose: bool
    lpm_model_name: str
    directory_lpm: Path
    run_reachable_concentrations: bool
    run_objective_function: bool
    run_calibration_metropolis_hastings: bool
    run_calibration_simplex: bool
    reachable_concentration_nmodels: int
    objective_function_nmodels: int
    mh_nstep: int
    mh_prior_option: bool
    mh_likelihood: bool
    mh_monitor: bool
    mh_display_traj: bool
    simplex_init_multiples_n: int
    simplex_fuq_n: int


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

    dataset_params = data.get("dataset", {})
    lpm_params = data.get("lpm", {})
    run_params = data.get("run", {})
    reach_params = data.get("reachable_concentrations", {})
    obj_params = data.get("objective_function", {})
    mh_params = data.get("calibration_metropolis_hastings", {})
    simplex_params = data.get("calibration_simplex", {})

    dataset_data_dir = Path(dataset_params.get("data_dir", "examples/data"))
    if not dataset_data_dir.is_absolute():
        dataset_data_dir = root_dir / dataset_data_dir

    lpm_data_dir = Path(lpm_params.get("data_directory", "core_data/LPM_data"))
    if not lpm_data_dir.is_absolute():
        lpm_data_dir = root_dir / lpm_data_dir

    return LauncherParams(
        dataset_name=dataset_params.get("name", "example_dataset"),
        dataset_year=dataset_params.get("year", 2010),
        dataset_data_dir=dataset_data_dir,
        verbose=bool(dataset_params.get("verbose", True)),
        lpm_model_name=lpm_params.get("model_name", "dirac_double"),
        directory_lpm=lpm_data_dir,
        run_reachable_concentrations=bool(run_params.get("reachable_concentrations", True)),
        run_objective_function=bool(run_params.get("objective_function", True)),
        run_calibration_metropolis_hastings=bool(
            run_params.get("calibration_metropolis_hastings", True)
        ),
        run_calibration_simplex=bool(run_params.get("calibration_simplex", True)),
        reachable_concentration_nmodels=int(reach_params.get("nmodels", 5000)),
        objective_function_nmodels=int(obj_params.get("nmodels", 10000)),
        mh_nstep=int(mh_params.get("nstep", 5000)),
        mh_prior_option=bool(mh_params.get("prior_option", False)),
        mh_likelihood=bool(mh_params.get("likelihood", True)),
        mh_monitor=bool(mh_params.get("monitor", False)),
        mh_display_traj=bool(mh_params.get("display_traj", False)),
        simplex_init_multiples_n=int(simplex_params.get("init_multiples_n", 3)),
        simplex_fuq_n=int(simplex_params.get("fuq_n", 30)),
    )
