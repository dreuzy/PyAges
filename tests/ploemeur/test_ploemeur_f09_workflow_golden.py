# -*- coding: utf-8 -*-
"""
Golden test for the Ploemeur F09 workflow (parameter summaries).
"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import pytest

from sites.ploemeur.workflows.ploemeur_workflow import (
    SimulationStrategy,
    load_workflow_params,
    validate_workflow_params,
)
from tests.utils import golden as golden_utils


GOLDEN_PATH = Path(__file__).resolve().parents[2] / "tests" / "golden" / "ploemeur_f09_workflow_values.json"
PARAMS_PATH = Path(__file__).resolve().parents[2] / "sites" / "ploemeur" / "params" / "ploemeur_F09.yaml"

TIME_SPAN_AND_PRIOR_MODES = (
    "successive_with_prior",
    "span_with_prior",
    "span_full",
    "cumulative",
    "successive",
)

PARAM_COLUMNS = {
    "exp_shifted": ["mu", "shift"],
    "ig_shifted": ["mu", "sigma", "shift"],
}


def _round_float(value: float, ndigits: int = 12) -> float:
    return float(np.round(value, ndigits))


def _extract_mode(file_root: str) -> str:
    for mode in TIME_SPAN_AND_PRIOR_MODES:
        if mode in file_root:
            return mode
    return "unknown"


def _collect_stats(stats_path: Path, lpm_type: str) -> Dict[str, float]:
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


def _objective_column(df: pd.DataFrame) -> Optional[str]:
    candidates = ("obj_function", "obj_func", "obj")
    for name in candidates:
        if name in df.columns:
            return name
    return None


def _collect_all_stats(root: Path) -> Dict[str, Dict[str, float]]:
    stats_files = list(root.rglob("lpm_stats_calibrated.txt"))
    if not stats_files:
        raise AssertionError(f"No calibration stats found under {root}")

    records: Dict[str, Dict[str, float]] = {}
    for stats_path in stats_files:
        rel = stats_path.relative_to(root)
        if len(rel.parts) < 6:
            continue
        file_root = rel.parts[0]
        well_date = rel.parts[-4]
        lpm_type = rel.parts[-3]
        mode = _extract_mode(file_root)
        record = _collect_stats(stats_path, lpm_type)
        key = f"mode={mode}|well_date={well_date}|lpm={lpm_type}"
        records[key] = record

    return records


@pytest.mark.extensive
def test_ploemeur_f09_workflow_golden(update_golden, tmp_path: Path) -> None:
    params = load_workflow_params(PARAMS_PATH)
    params["results"] = {"use_default": False, "directory": str(tmp_path)}
    params.setdefault("calibration", {})
    params["calibration"]["mh_nsteps"] = 200
    params["calibration"]["seed_enabled"] = True
    params["calibration"]["seed"] = 12345
    validate_workflow_params(params)

    prior_pipeline = params.get("workflows", {}).get("prior_pipeline", [])
    for pipeline in prior_pipeline:
        strategy = SimulationStrategy(prior_pipeline=pipeline, params=params)
        strategy.execute()

    record = _collect_all_stats(tmp_path)
    store = golden_utils.load_golden(GOLDEN_PATH)
    key = "ploemeur_F09_workflow"

    if update_golden:
        store[key] = record
        golden_utils.save_golden(GOLDEN_PATH, store)
        return

    assert key in store, f"Missing golden entry for {key}. Run with --update-golden."
    assert record == store[key]
