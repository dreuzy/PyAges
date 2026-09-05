# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Smoke tests for Albuquerque example configurations.
"""

from pathlib import Path

from pyages.lpm import build_lpm
from pyages.workflows.single_date.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    REPO_ROOT
    / "examples"
    / "natural"
    / "albuquerque"
    / "exemple_albuquerque_shapefree.yaml"
)
STARTER_CONFIG_PATH = (
    REPO_ROOT / "examples" / "natural" / "albuquerque" / "exemple_albuquerque.yaml"
)


def test_albuquerque_starter_avoids_unqualified_simplex_path():
    params = load_config(REPO_ROOT, STARTER_CONFIG_PATH)

    assert params.run.calibration_metropolis_hastings is True
    assert params.run.calibration_simplex is False


def test_albuquerque_shapefree_config_uses_local_lpm_directory():
    params = load_config(REPO_ROOT, CONFIG_PATH)
    lpm = build_lpm(
        params.lpm.model_name,
        directory_lpm=str(params.lpm.data_directory),
    )

    assert params.dataset.name == "SSW_2007.txt"
    assert params.lpm.model_name == "shapefree_n_oldbin"
    assert (
        params.lpm.data_directory
        == REPO_ROOT / "examples" / "natural" / "albuquerque" / "data_lpm"
    )
    assert params.run.reachable_concentrations is False
    assert params.run.objective_function is False
    assert params.run.calibration_metropolis_hastings is True
    assert params.run.calibration_simplex is False
    assert lpm.get_param_names() == ["z1", "z2", "z3", "z4"]
    assert lpm.bin_edges().tolist() == [0.0, 5.0, 15.0, 30.0, 45.0, 120.0]
