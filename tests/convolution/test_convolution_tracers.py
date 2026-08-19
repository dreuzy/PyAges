"""
Synthetic non-regression tests for ConvolutionTracers.

Focus:
- deterministic sampling via fixed RNG
- stable aggregate stats for golden checks
"""

from pathlib import Path

import numpy as np
import pytest

import pyage.lpm.lpm_build as lpm_build_module
from pyage.convolution.convolution_tracers import ConvolutionTracers
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _golden_path() -> Path:
    return (
        test_paths.repo_root() / "tests" / "golden" / "convolution_tracers_values.json"
    )


def _lpm_types() -> list[str]:
    types = lpm_build_module.list_available_lpms()
    return sorted(t for t in types if t != "mix_exp_shifted")


LPM_NAMES = _lpm_types()
TRACER_NAMES = ["cfc11", "cfc12", "cfc113"]
DATE = 2010.0


@pytest.mark.parametrize("lpm_name", LPM_NAMES)
def test_convolution_tracers_golden(lpm_name, update_golden):
    rng = np.random.default_rng(12345)
    lpm = lpm_build_module.lpm_build_random_uniform(lpm_name, rng=rng)
    tracers = ConvolutionTracers(names=TRACER_NAMES, date=DATE)

    concentrations = tracers.convolve(
        lpm,
        return_type="concentrations",
    )
    df = tracers.convolve(lpm, return_type="dataframe")

    stats = {
        "mean_concentration": float(concentrations.cv["concentration"].mean()),
        "mean_error": float(concentrations.cv["error"].mean()),
        "dataframe_mean_concentration": float(df["concentration"].mean()),
    }

    key = f"{lpm_name}:date={DATE}:tracers={','.join(TRACER_NAMES)}"
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        store[key] = stats
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]
    assert stats["mean_concentration"] == pytest.approx(
        expected["mean_concentration"], rel=1e-6, abs=1e-6
    )
    assert stats["mean_error"] == pytest.approx(
        expected["mean_error"], rel=1e-6, abs=1e-6
    )
    assert stats["dataframe_mean_concentration"] == pytest.approx(
        expected["dataframe_mean_concentration"], rel=1e-6, abs=1e-6
    )
