"""Tests for LPM params.yaml loader."""

from pathlib import Path

import pytest

from data_io import lpm_params


def _models() -> list[str]:
    return sorted(d.name for d in _data_dir().iterdir() if d.is_dir())


def _data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sources" / "LPM_data"


@pytest.mark.parametrize("model_name", _models())
def test_load_params_smoke(model_name):
    params = lpm_params.load_params(model_name, _data_dir())
    assert params["model"] == model_name


@pytest.mark.parametrize("model_name", _models())
def test_bounds_init_steps_priors(model_name):
    params = lpm_params.load_params(model_name, _data_dir())
    bounds = lpm_params.get_bounds(params)
    init = lpm_params.get_init(params)
    steps = lpm_params.get_steps(params)
    priors = lpm_params.get_priors(params)

    assert bounds
    assert init
    assert steps
    assert priors
