# -*- coding: utf-8 -*-
"""
Golden test for the temporal MH launcher (span mode, multi-date file).
"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml

from pyage.workflows.temporal import run_temporal
from tests.utils import golden as golden_utils


GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "golden"
    / "ploemeur_temporal_values.json"
)
PARAMS_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "ploemeur_temporal"
    / "ploemeur_temporal.yaml"
)

PARAM_COLUMNS = {
    "exp_shifted": ["mu", "shift"],
    "ig": ["mu", "sigma"],
    "ig_shifted": ["mu", "sigma", "shift"],
}


def _round_float(value: float, ndigits: int = 12) -> float:
    return float(np.round(value, ndigits))


def _objective_column(df: pd.DataFrame) -> Optional[str]:
    for name in ("obj_function", "obj_func", "obj"):
        if name in df.columns:
            return name
    return None


def _stats_from_file(stats_path: Path, lpm_type: str) -> Dict[str, float]:
    df = pd.read_csv(stats_path, sep="\t", index_col=0)
    if lpm_type not in PARAM_COLUMNS:
        raise ValueError(f"Unsupported LPM type for golden stats: {lpm_type}")
    cols = PARAM_COLUMNS[lpm_type]
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in stats file {stats_path}: {missing}")
    mean_row = df.loc["mean", cols].astype(float)
    std_row = df.loc["std", cols].astype(float)
    count_val = float(df.loc["count", cols[0]])
    record = {"count": _round_float(count_val)}
    for col in cols:
        record[f"{col}_mean"] = _round_float(float(mean_row[col]))
        record[f"{col}_std"] = _round_float(float(std_row[col]))
    obj_col = _objective_column(df)
    if obj_col:
        record["obj_mean"] = _round_float(float(df.loc["mean", obj_col]))
        record["obj_std"] = _round_float(float(df.loc["std", obj_col]))
    return record


def _load_params(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _assert_record_close(actual: Dict, expected: Dict, tol: float = 1e-4) -> None:
    """Assert that two nested dicts of numeric values are close within tolerance."""
    assert actual.keys() == expected.keys(), (
        f"Golden keys mismatch: {actual.keys()} vs {expected.keys()}"
    )
    for key, actual_value in actual.items():
        expected_value = expected[key]
        if isinstance(actual_value, dict) and isinstance(expected_value, dict):
            _assert_record_close(actual_value, expected_value, tol=tol)
            continue
        if isinstance(actual_value, (int, float)) and isinstance(
            expected_value, (int, float)
        ):
            assert np.isclose(actual_value, expected_value, atol=0, rtol=tol), (
                f"Value mismatch for {key}: {actual_value} != {expected_value} (tol={tol})"
            )
            continue
        assert actual_value == expected_value, (
            f"Value mismatch for {key}: {actual_value} != {expected_value}"
        )


def test_ploemeur_temporal_golden(update_golden, tmp_path: Path) -> None:
    params = _load_params(PARAMS_PATH)
    params["results"] = {
        "use_default": False,
        "directory": str(tmp_path),
        "study_name": "ploemeur_temporal",
    }
    params.setdefault("calibration", {})
    params["calibration"]["mh_nsteps"] = 200
    params["calibration"]["seed_enabled"] = True
    params["calibration"]["seed"] = 12345
    params["figures"] = {"temporal": False, "distributions": False}
    params["workflow"] = {"mode": "span"}

    params_path = tmp_path / "ploemeur_temporal_test.yaml"
    with params_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(params, handle, sort_keys=False)

    run_temporal(params_path)

    dataset_file = Path(params["dataset"]["file"])
    dataset_stem = dataset_file.stem
    mode = params["workflow"]["mode"]
    lpm_list: List[str] = params.get("lpm_models", {}).get("list") or []

    results_root = tmp_path / "ploemeur_temporal" / dataset_stem / mode / "span_full"
    record: Dict[str, Dict[str, float]] = {}
    for lpm_type in lpm_list:
        stats_path = results_root / lpm_type / "lpm_stats_calibrated.txt"
        record[f"mode={mode}|lpm={lpm_type}"] = _stats_from_file(stats_path, lpm_type)

    store = golden_utils.load_golden(GOLDEN_PATH)
    key = f"ploemeur_temporal|{dataset_stem}|{mode}"

    if update_golden:
        store[key] = record
        golden_utils.save_golden(GOLDEN_PATH, store)
        return

    assert key in store, f"Missing golden entry for {key}. Run with --update-golden."
    _assert_record_close(record, store[key], tol=1e-4)
