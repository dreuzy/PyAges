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

import json
from pathlib import Path

import numpy as np
import pytest

import global_parameters as gp
from convolutions.concentrations import Concentrations


def _repo_root() -> Path:
    # repo_root/tests/convolutions/test_concentrations.py -> repo_root
    return Path(__file__).resolve().parents[2]


def _tests_data_dir() -> Path:
    # Test fixtures live under tests/data
    return _repo_root() / "tests" / "data"


def _golden_path() -> Path:
    # Golden values file for concentration aggregates
    return _repo_root() / "tests" / "golden" / "concentrations_values.json"


def _load_golden() -> dict:
    # Local helper to keep this test file self-contained.
    path = _golden_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_golden(store: dict) -> None:
    # Atomic write to avoid partial JSON on interruption.
    path = _golden_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(store, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


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
    store = _load_golden()

    if update_golden:
        store[key] = stats
        _save_golden(store)
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
