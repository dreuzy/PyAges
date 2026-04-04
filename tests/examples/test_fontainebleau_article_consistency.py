# -*- coding: utf-8 -*-
"""
Consistency checks between the Fontainebleau example data and the source paper.
"""

from pathlib import Path

import pandas as pd


DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "fontainebleau"
    / "data"
)
CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "natural"
    / "fontainebleau"
    / "exemple_fontainebleau.yaml"
)


# Table 4 in:
# Corcho Alvarado et al. (2007), Water Resources Research 43, W03427.
ARTICLE_TABLE_4 = {
    "SM": {"kr85": (43.0, 5.0), "3H": (10.0, 0.8), "39Ar": (79.0, 7.0), "14C": (80.2, 0.6)},
    "CGEB": {"kr85": (6.8, 0.7), "3H": (8.5, 0.8), "39Ar": (73.0, 5.0), "14C": (75.1, 0.6)},
    "SA": {"kr85": (16.1, 4.1), "3H": (15.1, 0.8), "39Ar": (69.0, 5.0), "14C": (84.2, 0.6)},
    "LRN10": {"kr85": (6.1, 4.8), "3H": (7.8, 0.8), "39Ar": (77.0, 5.0), "14C": (73.7, 0.6)},
    "IMR": {"kr85": (2.9, 0.4), "3H": (3.1, 0.8), "39Ar": (55.0, 5.0), "14C": (69.8, 0.6)},
    "SLP4": {"kr85": (6.2, 2.5), "3H": (7.8, 0.8), "39Ar": (59.0, 5.0), "14C": (75.5, 0.6)},
    "SLP5": {"kr85": (5.6, 2.8), "3H": (4.0, 0.8), "39Ar": (51.0, 5.0), "14C": (73.8, 0.6)},
}


def _load_dataset(site_code: str) -> pd.DataFrame:
    path = DATA_DIR / f"fontainebleau_{site_code}"
    return pd.read_csv(path, sep=r"\s+", engine="python")


def test_fontainebleau_article_site_set():
    observed = {
        path.name.removeprefix("fontainebleau_")
        for path in DATA_DIR.glob("fontainebleau_*")
        if path.is_file()
    }
    assert observed == set(ARTICLE_TABLE_4)


def test_fontainebleau_article_table_4_values():
    for site_code, expected in ARTICLE_TABLE_4.items():
        frame = _load_dataset(site_code)

        for tracer in ("kr85", "3H", "14C"):
            row = frame.loc[frame["element"] == tracer].iloc[0]
            concentration, error = expected[tracer]
            assert float(row["concentration"]) == concentration
            assert float(row["error"]) == error

        ar39_row = frame.loc[frame["element"] == "39Ar"].iloc[0]
        ar39_concentration, ar39_error = expected["39Ar"]
        assert round(float(ar39_row["concentration"]) * 100.0, 12) == ar39_concentration
        assert round(float(ar39_row["error"]) * 100.0, 12) == ar39_error
        assert str(ar39_row["unit"]) == "%modern"


def test_fontainebleau_sampling_campaign_year():
    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    assert "year: 2001" in config_text
