# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regression contracts for the tracer data distributed with PyAges."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from pyages.tracer.decay import rate_from_half_life
from pyages.tracer.tracer_root import Tracer

DATA_TRACER_DIR = Path(__file__).resolve().parents[2] / "data_core" / "data_tracer"


def _tracer(name: str) -> Tracer:
    return Tracer(DATA_TRACER_DIR, name=name)


def _chronicle(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_TRACER_DIR / name / "recharge.csv", comment="#")


@pytest.mark.parametrize(
    ("name", "datemin", "datemax", "point_count"),
    [
        ("cfc11", 1940.0, 2025.0, 171),
        ("cfc12", 1940.0, 2025.0, 171),
        ("cfc113", 1940.0, 2025.0, 171),
        ("sf6", 1940.0, 2023.0, 167),
    ],
)
def test_stable_atmospheric_tracer_contract(
    name: str, datemin: float, datemax: float, point_count: int
) -> None:
    tracer = _tracer(name)
    chronicle = _chronicle(name)

    assert list(chronicle.columns) == ["date", "concentration"]
    assert len(chronicle) == point_count
    assert tracer.unit == "pptv"
    assert tracer.datemin == datemin
    assert tracer.datemax == datemax

    # No decay and no production: elapsed time leaves the input unchanged.
    initial = tracer.get_concentration(date=datemin, time=0.0)
    assert tracer.get_concentration(date=datemin, time=37.0) == pytest.approx(initial)


def test_cfc12_header_preserves_first_record() -> None:
    tracer = _tracer("cfc12")

    assert tracer.get_concentration(date=1940.0, time=0.0) == pytest.approx(0.34)


def test_tritium_distributed_metadata_and_decay() -> None:
    tracer = _tracer("3H")
    chronicle = _chronicle("3H")

    assert len(chronicle) == 106
    assert tracer.unit == "TU"
    assert tracer.datemin == 1957.5
    assert tracer.datemax == 2010.0
    assert rate_from_half_life(12.32) == pytest.approx(math.log(2.0) / 12.32)

    initial = tracer.get_concentration(date=2000.0, time=0.0)
    assert tracer.get_concentration(date=2000.0, time=12.32) == pytest.approx(
        initial / 2.0
    )
    # Outside the chronicle the input is zero; zero output therefore confirms
    # that no in-situ production term is configured.
    assert tracer.get_concentration(date=1900.0, time=100.0) == pytest.approx(0.0)


def test_argon39_distributed_metadata_and_decay() -> None:
    tracer = _tracer("39Ar")

    assert tracer.unit == "fraction_modern"
    assert tracer.get_concentration(date=2000.0, time=0.0) == pytest.approx(1.0)
    assert tracer.get_concentration(date=2000.0, time=267.0) == pytest.approx(0.5)
    assert rate_from_half_life(267.0) == pytest.approx(math.log(2.0) / 267.0)


def test_carbon14_variants_have_distinct_canonical_recharge_contracts() -> None:
    generic = _tracer("14C")
    north = _tracer("14C_NH")
    south = _tracer("14C_SH")

    assert generic.unit == north.unit == south.unit == "pmC"
    assert generic.get_concentration(date=2000.0, time=0.0) == pytest.approx(100.0)
    assert north.convolution_dates is not None
    assert south.convolution_dates is not None
    assert generic.convolution_dates is None
    for tracer in (generic, north, south):
        initial = tracer.get_concentration(date=2000.0, time=0.0)
        assert tracer.get_concentration(date=2000.0, time=5730.0) == pytest.approx(
            initial / 2.0
        )


def test_every_carbon14_directory_has_one_canonical_yaml() -> None:
    for name in ("14C", "14C_NH", "14C_SH"):
        yaml_files = sorted(
            path.name for path in (DATA_TRACER_DIR / name).glob("*.yaml")
        )
        assert yaml_files == [f"{name}.yaml"]
