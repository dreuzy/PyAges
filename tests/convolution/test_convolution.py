"""
Synthetic smoke tests for convolution (Convolution + LPM).

Goal: validate that convolution runs and returns finite values for a small set
of tracers/LPMs without asserting scientific correctness.
"""

import math
from pathlib import Path
import numpy as np
import pytest

from pyage.lpm.lpm_build import lpm_build, list_available_lpms
import pyage.tracer.tracer_root as tracer_module
from pyage.convolution.convolution import Convolution
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _lpm_types() -> list[str]:
    types = list_available_lpms()
    return sorted(t for t in types if t != "mix_exp_shifted")


def _golden_path() -> Path:
    return test_paths.repo_root() / "tests" / "golden" / "convolution_values.json"


@pytest.mark.parametrize("lpm_type", _lpm_types())
@pytest.mark.parametrize("tracer_name", ["cfc11", "kr85", "cfc12", "cfc113", "sf6"])
def test_convolution_value_finite(lpm_type, tracer_name):
    lpm = lpm_build(lpm_type, directory_lpm=str(test_paths.lpm_data_dir()))
    try:
        lpm.set_param_from_array(lpm.param_init())
    except Exception:
        pass

    tracer = tracer_module.Tracer(test_paths.tracer_data_dir(), tracer_name)
    conv = Convolution(tracer, date=2010.0)
    value = conv.convolution(lpm, prepare=False, opt=True)
    assert math.isfinite(float(value))


def test_convolution_date_range_dataframe():
    lpm = lpm_build("exp", directory_lpm=str(test_paths.lpm_data_dir()))
    tracer = tracer_module.Tracer(test_paths.tracer_data_dir(), "cfc11")
    conv = Convolution(tracer, date=2010.0)

    df = conv.convolution_date_range(lpm, 2000.0, 2005.0)
    assert list(df.columns) == ["date", "concentration", "element"]
    assert len(df) > 0
    assert np.all(np.isfinite(df["concentration"].to_numpy()))


@pytest.mark.parametrize("lpm_type", _lpm_types())
@pytest.mark.parametrize("tracer_name", ["cfc11", "kr85", "cfc12", "cfc113", "sf6"])
def test_convolution_golden_at_date_2010(lpm_type, tracer_name, update_golden):
    lpm = lpm_build(lpm_type, directory_lpm=str(test_paths.lpm_data_dir()))
    try:
        lpm.set_param_from_array(lpm.param_init())
    except Exception:
        pass

    tracer = tracer_module.Tracer(test_paths.tracer_data_dir(), tracer_name)
    conv = Convolution(tracer, date=2010.0)
    value = float(conv.convolution(lpm, prepare=False, opt=True))

    key = f"{lpm_type}:{tracer_name}:date=2010.0"
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        store[key] = value
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(
            f"Golden value missing for {key}. "
            f"Run: pytest -s --update-golden"
        )

    expected = float(store[key])
    assert value == pytest.approx(expected, rel=1e-6, abs=1e-6)
