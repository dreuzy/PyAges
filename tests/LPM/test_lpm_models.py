"""
Non-regression tests for all LPM models (pdf/cdf/cdf_inv + basic invariants).

- Auto-discovers model types from the LPM registry.
- Uses golden values stored in tests/golden/lpm_values.json.
- Supports --update-golden to refresh reference values.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from pyage.LPM.lpm_build import lpm_build, list_available_lpms
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _lpm_types() -> list[str]:
    types = list_available_lpms()
    return sorted(t for t in types if t != "mix_exp_shifted")


def _golden_path() -> Path:
    return test_paths.repo_root() / "tests" / "golden" / "lpm_values.json"


def _make_lpm(lpm_type: str):
    # Instantiate the LPM using local data_LPM; keep defaults if init fails.
    lpm = lpm_build(lpm_type, directory_lpm=str(test_paths.lpm_data_dir()))
    try:
        lpm.set_param_from_array(lpm.param_init())
    except Exception:
        # Keep default parameters if init file is missing or invalid.
        pass
    return lpm


@pytest.mark.parametrize("lpm_type", _lpm_types())
def test_lpm_smoke_all(lpm_type):
    # Basic invariants for every LPM implementation.
    lpm = _make_lpm(lpm_type)

    assert lpm.name == lpm_type

    rng = np.random.default_rng(12345)
    lpm.random_uniform(rng=rng)
    assert lpm.param_within_bounds(lpm.p)

    params = lpm.get_parameters_to_array()
    lpm.set_param_from_array(params)
    assert lpm.param_within_bounds(lpm.p)

    mean_val = lpm.mean()
    std_val = lpm.std()
    assert math.isfinite(mean_val)
    assert math.isfinite(std_val)
    assert std_val >= 0

    t = np.array([0.0, 1.0, 10.0])
    pdf_vals = lpm.pdf(t)
    assert np.all(np.isfinite(pdf_vals))
    assert np.all(pdf_vals >= 0)


@pytest.mark.parametrize("lpm_type", _lpm_types())
def test_lpm_golden_pdf_cdf_cdf_inv(lpm_type, update_golden):
    # Golden values for a mid-quantile point p0.
    lpm = _make_lpm(lpm_type)

    p0 = 0.5
    t0 = float(lpm.cdf_inv(p0))

    pdf_val = float(np.asarray(lpm.pdf(np.array([t0])))[0])
    cdf_val = float(np.asarray(lpm.cdf(np.array([t0])))[0])
    cdf_inv_val = float(lpm.cdf_inv(p0))

    key = lpm_type
    store = golden_utils.load_golden(_golden_path())

    record = {
        "pdf": {"t": t0, "value": pdf_val},
        "cdf": {"t": t0, "value": cdf_val},
        "cdf_inv": {"p": p0, "value": cdf_inv_val},
    }

    if update_golden:
        store[key] = record
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(
            f"Golden value missing for {key}. "
            f"Run: pytest -s --update-golden"
        )

    expected = store[key]
    assert t0 == pytest.approx(expected["pdf"]["t"], rel=1e-6, abs=1e-6)
    assert pdf_val == pytest.approx(expected["pdf"]["value"], rel=1e-6, abs=1e-6)
    assert cdf_val == pytest.approx(expected["cdf"]["value"], rel=1e-6, abs=1e-6)
    assert cdf_inv_val == pytest.approx(expected["cdf_inv"]["value"], rel=1e-6, abs=1e-6)
