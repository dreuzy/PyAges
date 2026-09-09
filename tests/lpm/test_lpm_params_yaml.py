# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Validation tests for LPM params.yaml files.

Checks presence of required fields and basic consistency across all models.
"""

from pathlib import Path

import pytest
import yaml

from pyages.lpm import build_lpm
from tests.utils import paths as test_paths


def _lpm_data_dir() -> Path:
    return test_paths.repo_root() / "data_core" / "data_lpm"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.mark.parametrize("model_dir", sorted(_lpm_data_dir().iterdir()))
def test_params_yaml_schema(model_dir: Path):
    if not model_dir.is_dir():
        pytest.skip("Not a directory")

    params_path = model_dir / "params.yaml"
    if not params_path.exists():
        pytest.fail(f"Missing params.yaml in {model_dir}")

    data = _load_yaml(params_path)
    assert data.get("model") == model_dir.name
    assert "parameters" in data
    params = data["parameters"]
    assert isinstance(params, list) and len(params) > 0

    for param in params:
        assert "name" in param
        assert "domain" in param
        assert "calibration_range" in param
        assert len(param["calibration_range"]) == 2
        assert "init" in param
        assert "step" in param
        prior = param.get("prior")
        assert prior and "type" in prior


@pytest.mark.parametrize(
    "model_name",
    ["dirac_double", "dirac_double_1_set", "mix_exp_shifted"],
)
def test_mixture_rate_metadata_is_dimensionless(model_name: str):
    data = _load_yaml(_lpm_data_dir() / model_name / "params.yaml")
    rate = next(param for param in data["parameters"] if param["name"] == "rate")

    assert rate["unit"] == "-"
    assert rate["prior"]["unit"] == "-"


@pytest.mark.parametrize("model_dir", sorted(_lpm_data_dir().iterdir()))
def test_runtime_parameter_units_match_yaml(model_dir: Path):
    if not model_dir.is_dir():
        pytest.skip("Not a directory")

    data = _load_yaml(model_dir / "params.yaml")
    yaml_units = {
        parameter["name"]: str(parameter.get("unit", ""))
        for parameter in data["parameters"]
    }
    model = build_lpm(model_dir.name, directory_lpm=_lpm_data_dir())

    assert model.parameter_units == yaml_units
