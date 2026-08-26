# -*- coding: utf-8 -*-
"""
Smoke test for concentration chronicles plotting helpers.
"""

from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg", force=True)

from pyage.concentrations import concentrations_time as ct
from pyage.config.runtime import DisplayOptions
from pyage.lpm.core import lpm_dist as LPM_dist
from pyage.lpm.lpm_build import lpm_build
from pyage.observations.loader import load_concentrations
from tests.utils import golden as golden_utils
from tests.utils import paths as test_paths


def _golden_path() -> Path:
    return (
        test_paths.repo_root()
        / "tests"
        / "golden"
        / "concentration_chronicles_values.json"
    )


def _summarize_concentrations(table: pd.DataFrame) -> dict[str, float]:
    stats: dict[str, float] = {"rows": int(len(table))}
    for col in table.columns:
        if col == "date":
            continue
        series = table[col].dropna()
        stats[f"{col}_mean"] = float(series.mean())
        stats[f"{col}_min"] = float(series.min())
        stats[f"{col}_max"] = float(series.max())
    return stats


def test_concentration_chronicles_smoke(tmp_path, update_golden):
    """
    Ensure concentration chronicles plotting runs and writes outputs.
    """
    well = "F09"
    dates = "2005_2024"
    data_path = (
        test_paths.repo_root()
        / "examples"
        / "natural"
        / "ploemeur_temporal"
        / "data"
        / "ori_ploemeur_F09_2005_2024.txt"
    )
    craw = load_concentrations(data_path)

    display = DisplayOptions()
    display.text = False
    display.figure = True
    display.figure_close = True
    display.figure_save = True
    display.directory = tmp_path

    conc_data = ct.ConcentrationTime(craw=craw)
    conc_data.save_to_file(tmp_path / "concentrations_wide.txt")

    # Build a minimal LpmDist with one parameter set to exercise plotting path.
    lpm = lpm_build("exp_shifted")
    lpm_results = LPM_dist.LpmDist(lpm, craw.names_dates())
    lpm_results.append_sample(
        lpm.p,
        obj_function=0.0,
        concentrations=[0.0] * len(craw.names_dates()),
    )
    ct.display_concentration_chronicles(
        craw,
        lpm_results,
        "smoke",
        display,
        lpm_number=1,
    )

    assert (tmp_path / "concentrations_wide.txt").exists()
    out_dir = tmp_path / "smoke"
    out_table = out_dir / "concentrations_all_models.txt"
    assert (out_dir / "concentration_times.png").exists()
    assert out_table.exists()

    table = pd.read_table(out_table, sep="\t")
    stats = _summarize_concentrations(table)
    key = f"{well}_{dates}_exp_shifted_successive"
    store = golden_utils.load_golden(_golden_path())

    if update_golden:
        store[key] = stats
        golden_utils.save_golden(_golden_path(), store)
        pytest.skip(f"Golden updated for {key}")

    if key not in store:
        pytest.fail(f"Golden value missing for {key}. Run: pytest -s --update-golden")

    expected = store[key]
    for stat_key, value in stats.items():
        assert value == pytest.approx(expected[stat_key], rel=1e-6, abs=1e-6)
