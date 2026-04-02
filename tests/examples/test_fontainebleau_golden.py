# -*- coding: utf-8 -*-
"""
Golden test for the Fontainebleau example dataset.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import pyage.concentrations.concentrations as co
from tests.utils import golden as golden_utils


GOLDEN_PATH = Path(__file__).resolve().parents[2] / "tests" / "golden" / "fontainebleau_example_values.json"
DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "fontainebleau"
    / "data"
    / "fontainebleau_CGEB"
)


def _round_float(value: float, ndigits: int = 12) -> float:
    return float(np.round(value, ndigits))


def _record_from_data(frame: pd.DataFrame) -> dict:
    elements = frame["element"].astype(str).tolist()
    return {
        "count": int(frame.shape[0]),
        "elements": elements,
        "mean_concentration": _round_float(frame["concentration"].mean()),
        "mean_error": _round_float(frame["error"].mean()),
        "mean_date": _round_float(frame["date"].mean()),
    }


def test_fontainebleau_golden(update_golden):
    conc = co.Concentrations(file_load=True, file_name=str(DATA_PATH))
    record = _record_from_data(conc.cv)

    store = golden_utils.load_golden(GOLDEN_PATH)
    key = DATA_PATH.name

    if update_golden:
        store[key] = record
        golden_utils.save_golden(GOLDEN_PATH, store)
        return

    assert key in store, f"Missing golden entry for {key}. Run with --update-golden."
    assert record == store[key]
