from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pyage.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
    ERROR_COLUMN,
    UNIT_COLUMN,
)
from sites.ploemeur.scripts.prepare_observations import prepare_well


def _write_raw(directory: Path, contents: str) -> None:
    (directory / "F09_brut.txt").write_text(contents, encoding="utf-8")


def test_prepare_well_writes_canonical_observations(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    output_directory = tmp_path / "ori"
    raw_directory.mkdir()
    _write_raw(
        raw_directory,
        "element\tCFC-11\tCFC-12\tCFC-113\n"
        "unit\tpptv\tpptv\tpptv\n"
        "09/06/2005\t278.1\t661.1\t99.8\n"
        "04/07/2006\t241.2\t0\t-1\n",
    )

    destination = prepare_well("F09", raw_directory, output_directory)

    assert destination.name == "ori_ploemeur_F09_2005_2006.txt"
    observations = pd.read_table(destination)
    assert list(observations.columns) == [
        ELEMENT_COLUMN,
        CONCENTRATION_COLUMN,
        ERROR_COLUMN,
        UNIT_COLUMN,
        DATE_COLUMN,
    ]
    assert observations[ELEMENT_COLUMN].tolist() == [
        "cfc11",
        "cfc12",
        "cfc113",
        "cfc11",
    ]
    assert observations[CONCENTRATION_COLUMN].tolist() == [278.1, 661.1, 99.8, 241.2]
    assert observations[ERROR_COLUMN].tolist() == [0.0] * 4
    assert observations[UNIT_COLUMN].tolist() == ["pptv"] * 4
    assert observations[DATE_COLUMN].tolist() == pytest.approx(
        [2005 + 159 / 365] * 3 + [2006 + 184 / 365]
    )


def test_prepare_well_uses_true_calendar_year_for_leap_year(tmp_path: Path) -> None:
    raw_directory = tmp_path / "raw"
    output_directory = tmp_path / "ori"
    raw_directory.mkdir()
    _write_raw(
        raw_directory,
        "element\tCFC-11\nunit\tpptv\n01/03/2024\t1.0\n31/10/2024\t2.0\n",
    )

    destination = prepare_well("F09", raw_directory, output_directory)
    observations = pd.read_table(destination)

    assert observations[DATE_COLUMN].tolist() == pytest.approx(
        [2024 + 60 / 366, 2024 + 304 / 366]
    )


@pytest.mark.parametrize(
    "header, unit",
    [("SF6", "pptv"), ("CFC-11", "pmol/kg")],
)
def test_prepare_well_rejects_unsupported_schema(
    tmp_path: Path,
    header: str,
    unit: str,
) -> None:
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    _write_raw(
        raw_directory,
        f"element\t{header}\nunit\t{unit}\n09/06/2005\t1.0\n",
    )

    with pytest.raises(ValueError):
        prepare_well("F09", raw_directory, tmp_path / "ori")
