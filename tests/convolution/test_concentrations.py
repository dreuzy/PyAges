"""
Non-regression and smoke tests for Concentrations.

Focus:
- basic loading/normalization
- stable aggregates for golden checks

Targets:
- data_test_exp.txt
- data_test_exp_with_errors.txt
- ori_ploemeur_F11_2004_2020.txt
"""

from pathlib import Path

import numpy as np
import pytest

import pyage.global_parameters as gp
from pyage.concentrations.concentrations import Concentrations
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _tests_data_dir() -> Path:
    # Test fixtures live under tests/data
    return test_paths.repo_root() / "tests" / "data"


def _golden_path() -> Path:
    # Golden values file for concentration aggregates
    return test_paths.repo_root() / "tests" / "golden" / "concentrations_values.json"


@pytest.mark.parametrize(
    "file_path",
    [
        _tests_data_dir() / "data_test_exp.txt",
        _tests_data_dir() / "data_test_exp_with_errors.txt",
        _tests_data_dir() / "ori_ploemeur_F11_2004_2020.txt",
    ],
)
def test_concentrations_load_smoke(file_path):
    # Basic load + column normalization checks.
    conc = Concentrations(file_load=True, file_name=str(file_path))

    # Columns are normalized and ordered
    assert list(conc.cv.columns) == gp.REFERENCE_COLUMNS

    # Basic sanity checks
    assert len(conc.cv) > 0
    assert np.all(np.isfinite(conc.cv["concentration"].to_numpy()))


def test_concentrations_load_basic():
    # Replacement for legacy test_load helper.
    file_path = _tests_data_dir() / "data_test_exp.txt"
    conc = Concentrations(file_load=True, file_name=str(file_path))
    assert not conc.cv.empty


@pytest.mark.parametrize(
    "file_path",
    [
        _tests_data_dir() / "data_test_exp.txt",
        _tests_data_dir() / "data_test_exp_with_errors.txt",
        _tests_data_dir() / "ori_ploemeur_F11_2004_2020.txt",
    ],
)
def test_concentrations_golden_stats(file_path, update_golden):
    # Golden aggregates for stability across refactors.
    conc = Concentrations(file_load=True, file_name=str(file_path))

    # Deterministic sampling for regression checks
    rng = np.random.default_rng(12345)
    sampled = conc.sample_concentrations_with_errors(rng)

    # Simple aggregate stats
    stats = {
        "mean_concentration": float(conc.cv["concentration"].mean()),
        "mean_error": float(conc.cv["error"].mean()),
        "sampled_mean_concentration": float(sampled.cv["concentration"].mean()),
    }

    key = file_path.name
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        store[key] = stats
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(
            f"Golden value missing for {key}. "
            f"Run: pytest -s --update-golden"
        )

    expected = store[key]
    assert stats["mean_concentration"] == pytest.approx(
        expected["mean_concentration"], rel=1e-6, abs=1e-6
    )
    assert stats["mean_error"] == pytest.approx(
        expected["mean_error"], rel=1e-6, abs=1e-6
    )
    assert stats["sampled_mean_concentration"] == pytest.approx(
        expected["sampled_mean_concentration"], rel=1e-6, abs=1e-6
    )
