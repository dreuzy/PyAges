# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Golden test for the Ploemeur example dataset.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from pyages.concentrations import Concentrations
from tests.utils import golden as golden_utils

GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "golden"
    / "ploemeur_example_values.json"
)
DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "ploemeur"
    / "data"
    / "ploemeur_F09_2010.txt"
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


def test_ploemeur_golden(update_golden):
    conc = Concentrations.from_file(DATA_PATH)
    record = _record_from_data(conc.frame)

    store = golden_utils.load_golden(GOLDEN_PATH)
    key = DATA_PATH.name

    if update_golden:
        store[key] = record
        golden_utils.save_golden(GOLDEN_PATH, store)
        return

    assert key in store, f"Missing golden entry for {key}. Run with --update-golden."
    assert record == store[key]
