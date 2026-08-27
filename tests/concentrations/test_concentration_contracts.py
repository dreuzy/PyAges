# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Unit contracts for validated concentration data and helper boundaries."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

from pyages.concentrations import Concentrations
from pyages.concentrations.concentrations_time import ConcentrationTime
from pyages.concentrations.schema import REFERENCE_COLUMNS
from pyages.concentrations.utils.plotting import plot_tracer_series
from pyages.concentrations.utils.storage import save_tracer_series_table
from pyages.concentrations.utils.tables import merge_model_into_table, to_cv_dict


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "element": ["cfc11", "cfc12"],
            "concentration": [1.0, 2.0],
            "date": [2000.0, 2001.0],
            "source": ["a", "b"],
        }
    )


def _series(tracer: str, dates=(2000.0, 2001.0)) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": dates,
            "concentration": np.arange(1, len(dates) + 1, dtype=float),
            "element": tracer,
        }
    )


def test_concentrations_normalizes_a_defensive_copy() -> None:
    source = _frame()
    concentrations = Concentrations.from_dataframe(source)

    source.loc[0, "concentration"] = 99.0
    assert list(concentrations.cv.columns) == list(REFERENCE_COLUMNS)
    assert concentrations.cv.loc[0, "concentration"] == 1.0
    assert concentrations.cv["error"].tolist() == [0.0, 0.0]
    assert concentrations.cv["unit"].tolist() == ["mol/l", "mol/l"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda frame: frame.drop(columns="date"), "Missing required columns"),
        (
            lambda frame: frame.assign(concentration=[1.0, np.inf]),
            "only finite values",
        ),
        (lambda frame: frame.assign(error=[0.0, -1.0]), "non-negative"),
        (lambda frame: frame.assign(element=["cfc11", " "]), "must not be empty"),
        (lambda frame: frame.iloc[0:0], "at least one observation"),
    ],
)
def test_concentrations_rejects_invalid_scientific_inputs(mutate, message) -> None:
    with pytest.raises(ValueError, match=message):
        Concentrations.from_dataframe(mutate(_frame()))


def test_concentrations_rejects_duplicate_columns() -> None:
    frame = _frame().rename(columns={"source": "date"})

    with pytest.raises(ValueError, match="Duplicate concentration columns"):
        Concentrations.from_dataframe(frame)


def test_error_assignment_validates_shape_fraction_and_sign() -> None:
    frame = _frame().assign(concentration=[-2.0, 4.0])
    concentrations = Concentrations.from_dataframe(frame)
    concentrations.error_affect_from_value(0.25)

    assert concentrations.cv["error"].tolist() == [0.5, 1.0]
    with pytest.raises(ValueError, match="non-negative"):
        concentrations.error_affect_from_value(-0.1)
    with pytest.raises(ValueError, match="exactly one value"):
        concentrations.error_affect_from_mean([1.0])
    with pytest.raises(ValueError, match="finite and non-negative"):
        concentrations.error_affect_from_mean([1.0, np.nan])


def test_error_assignment_from_mean_preserves_existing_errors() -> None:
    concentrations = Concentrations.from_dataframe(_frame().assign(error=[3.0, 0.0]))

    concentrations.error_affect_from_mean([10.0, 20.0], fraction=0.1)

    assert concentrations.cv["error"].tolist() == [3.0, 2.0]


def test_sampling_is_reproducible_and_does_not_mutate_source() -> None:
    concentrations = Concentrations.from_dataframe(_frame().assign(error=[0.5, 1.0]))

    sampled = concentrations.sample_concentrations_with_errors(
        np.random.default_rng(123)
    )

    assert concentrations.cv["concentration"].tolist() == [1.0, 2.0]
    assert sampled.cv["concentration"].to_numpy() == pytest.approx(
        [0.5054393248260746, 1.6322133485321169]
    )
    with pytest.raises(TypeError, match="numpy.random.Generator"):
        concentrations.sample_concentrations_with_errors(None)  # type: ignore[arg-type]


def test_figure_concentrations_uses_explicit_axes_and_rejects_negative_indices() -> (
    None
):
    concentrations = Concentrations.from_dataframe(_frame())
    fig, ax = plt.subplots()
    try:
        artist = concentrations.figure_concentrations(
            0, 1, label_x="x", label_y="y", ax=ax
        )
        assert artist.axes is ax
        assert ax.get_xlabel() == "x"
        assert ax.get_ylabel() == "y"
        with pytest.raises(IndexError, match="out of range"):
            concentrations.figure_concentrations(-1, 0, ax=ax)
    finally:
        plt.close(fig)


def test_concentration_time_requires_one_input_and_copies_series() -> None:
    raw = Concentrations.from_dataframe(_frame())
    with pytest.raises(ValueError, match="exactly one"):
        ConcentrationTime()
    with pytest.raises(ValueError, match="exactly one"):
        ConcentrationTime(craw=raw, cv={"cfc11": _series("cfc11")})

    source = {"cfc11": _series("cfc11")}
    chronicle = ConcentrationTime(cv=source)
    source["cfc11"].loc[0, "concentration"] = 999.0
    assert chronicle.cv["cfc11"].loc[0, "concentration"] == 1.0


def test_to_cv_dict_preserves_tracer_order_and_sorts_dates() -> None:
    frame = pd.concat(
        [
            _series("cfc12", dates=(2002.0, 2000.0)),
            _series("cfc11", dates=(2001.0,)),
        ],
        ignore_index=True,
    )

    series = to_cv_dict(frame)

    assert list(series) == ["cfc12", "cfc11"]
    assert series["cfc12"]["date"].tolist() == [2000.0, 2002.0]


def test_merge_model_uses_union_of_dates_without_mutating_input() -> None:
    previous = pd.DataFrame({"date": [1999.0], "legacy": [4.0]})
    merged = merge_model_into_table(
        previous,
        {
            "cfc11": _series("cfc11", dates=(2000.0, 2001.0)),
            "cfc12": _series("cfc12", dates=(2001.0, 2002.0)),
        },
        model_id=1,
    )

    assert previous.columns.tolist() == ["date", "legacy"]
    assert merged["date"].tolist() == [1999.0, 2000.0, 2001.0, 2002.0]
    assert merged.columns.tolist() == ["date", "legacy", "cfc11_1", "cfc12_1"]
    with pytest.raises(ValueError, match="already exists"):
        merge_model_into_table(merged, {"cfc11": _series("cfc11")}, model_id=1)
    with pytest.raises(ValueError, match="at least one tracer"):
        merge_model_into_table(None, {}, model_id=1)


def test_wide_export_rejects_ambiguous_duplicate_dates(tmp_path) -> None:
    duplicate = _series("cfc11", dates=(2000.0, 2000.0))

    with pytest.raises(ValueError, match="duplicate dates"):
        save_tracer_series_table({"cfc11": duplicate}, tmp_path / "series.tsv")


def test_plot_tracer_series_rejects_invalid_mode_and_insufficient_axes() -> None:
    series = {"cfc11": _series("cfc11"), "cfc12": _series("cfc12")}
    fig, ax = plt.subplots()
    try:
        with pytest.raises(ValueError, match="graph_type"):
            plot_tracer_series(series, [ax, ax], graph_type="bars")
        with pytest.raises(ValueError, match="Not enough axes"):
            plot_tracer_series(series, ax)
    finally:
        plt.close(fig)
