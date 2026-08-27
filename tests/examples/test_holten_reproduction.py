# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import numpy as np
import pytest

from examples.natural.holten.holten_reproduction import (
    BIN_ORDER,
    ForwardConvention,
    build_coupled_tritium_tracers,
    build_observations,
    build_reproduction_endmembers,
    parent_daughter_response,
)

pytest_plugins = ("tests.examples.holten_fixtures",)


def test_parent_daughter_response_uses_half_life_and_conserves_parent():
    initial = np.asarray([3.0, 12.0, 100.0])
    parent, daughter = parent_daughter_response(initial, 12.32, 12.32)

    assert parent == pytest.approx(initial / 2.0)
    assert daughter == pytest.approx(initial / 2.0)
    assert parent + daughter == pytest.approx(initial)


def test_coupled_synthetic_tracers_share_one_conservative_response(
    prepared_holten_case,
):
    convention = ForwardConvention("test", vadose_years=2.0, decay_during_vadose=True)
    tritium, helium = build_coupled_tritium_tracers(prepared_holten_case, convention)
    reference_year = float(prepared_holten_case.observed_aggregated["date"].median())
    ages = np.asarray([0.0, 10.0, 30.0, 50.0])

    parent = tritium.get_concentration(reference_year, ages)
    daughter = helium.get_concentration(reference_year, ages)

    assert np.all(np.asarray(parent) >= 0.0)
    assert np.all(np.asarray(daughter) >= 0.0)
    assert np.asarray(daughter)[0] == pytest.approx(0.0)
    assert np.all(np.isfinite(np.asarray(parent) + np.asarray(daughter)))


def test_reproduction_endmembers_and_observations_include_tritiogenic_helium(
    prepared_holten_case,
):
    convention = ForwardConvention("test", vadose_years=2.0, decay_during_vadose=True)
    endmembers = build_reproduction_endmembers(prepared_holten_case, convention)
    observations = build_observations(
        prepared_holten_case, "59-05", include_helium=True
    )

    assert set(endmembers["tracer"]) == {"3H", "3He_trit", "kr85", "39Ar"}
    assert endmembers.groupby("tracer")["bin_name"].apply(list).to_dict() == {
        "39Ar": BIN_ORDER,
        "3H": BIN_ORDER,
        "3He_trit": BIN_ORDER,
        "kr85": BIN_ORDER,
    }
    assert observations["element"].tolist() == ["3H", "3He_trit", "kr85", "39Ar"]
    helium = observations.loc[observations["element"] == "3He_trit"].iloc[0]
    assert helium["concentration"] == pytest.approx(21.1)
    assert helium["error"] == pytest.approx(0.5)
