# -*- coding: utf-8 -*-
"""
Smoke tests for Albuquerque example configurations.
"""

from pathlib import Path

from pyage.lpm.lpm_build import lpm_build
from pyage.workflows.single_date_config import load_params

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    REPO_ROOT
    / "examples"
    / "natural"
    / "albuquerque"
    / "exemple_albuquerque_shapefree.yaml"
)


def test_albuquerque_shapefree_config_uses_local_lpm_directory():
    params = load_params(REPO_ROOT, CONFIG_PATH)
    lpm = lpm_build(params.lpm_model_name, directory_lpm=str(params.directory_lpm))

    assert params.dataset_name == "SSW_2007.txt"
    assert params.lpm_model_name == "shapefree_n_oldbin"
    assert (
        params.directory_lpm
        == REPO_ROOT / "examples" / "natural" / "albuquerque" / "data_lpm"
    )
    assert params.run_reachable_concentrations is False
    assert params.run_objective_function is False
    assert params.run_calibration_metropolis_hastings is True
    assert params.run_calibration_simplex is False
    assert lpm.get_param_names() == ["z1", "z2", "z3", "z4"]
    assert lpm.bin_edges().tolist() == [0.0, 5.0, 15.0, 30.0, 45.0, 120.0]
