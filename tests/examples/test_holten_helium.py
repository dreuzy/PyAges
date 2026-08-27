# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import numpy as np
import pytest

from examples.natural.holten.holten_four_bin import (
    BIN_ORDER,
    LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM,
    _local_4bin_observations,
    build_4bin_endmembers,
    tritium_parent_daughter,
)

pytest_plugins = ("tests.examples.holten_fixtures",)


def test_tritium_parent_daughter_analytical_limits_and_conservation():
    initial = np.array([8.0, 8.0, 8.0])
    ages = np.array([0.0, 12.32, 12_320.0])

    parent, daughter = tritium_parent_daughter(
        initial,
        ages,
        half_life_years=12.32,
    )

    assert parent[0] == pytest.approx(8.0)
    assert daughter[0] == pytest.approx(0.0)
    assert parent[1] == pytest.approx(4.0)
    assert daughter[1] == pytest.approx(4.0)
    assert parent[-1] == pytest.approx(0.0, abs=1e-12)
    assert daughter[-1] == pytest.approx(8.0)
    np.testing.assert_allclose(parent + daughter, initial, rtol=0.0, atol=1e-12)


def test_tritium_parent_daughter_uses_half_life_not_mean_lifetime():
    parent, _ = tritium_parent_daughter(1.0, 1.0, half_life_years=12.32)

    assert float(parent) == pytest.approx(np.exp(-np.log(2.0) / 12.32))
    assert float(parent) != pytest.approx(np.exp(-1.0 / 12.32))


def test_tritium_parent_daughter_rejects_nonphysical_arguments():
    with pytest.raises(ValueError, match="half-life"):
        tritium_parent_daughter(1.0, 1.0, half_life_years=0.0)
    with pytest.raises(ValueError, match="non-negative"):
        tritium_parent_daughter(1.0, -1.0, half_life_years=12.32)


def test_h4_endmembers_and_observations_are_holten_local(prepared_holten_case):
    prepared = prepared_holten_case
    endmembers = build_4bin_endmembers(prepared, include_helium=True)
    helium = endmembers.loc[endmembers["tracer"] == "3He_trit"].set_index("bin_name")

    assert helium.index.tolist() == BIN_ORDER
    assert helium["unit"].unique().tolist() == ["TU_equivalent"]
    assert helium.loc["f_0_20", "concentration"] == pytest.approx(5.2307566891)
    assert helium.loc["f_20_40", "concentration"] == pytest.approx(58.3608406645)
    assert helium.loc["f_40_60", "concentration"] == pytest.approx(408.9516273728)
    assert helium.loc["f_old", "concentration"] == pytest.approx(2.8974192002)

    for well_id in prepared.context.selected_wells:
        observations = _local_4bin_observations(
            prepared,
            well_id,
            include_helium=True,
        )
        assert observations["element"].tolist() == list(
            LOCAL_4BIN_TRACER_ORDER_WITH_HELIUM
        )
        helium_observation = observations.loc[
            observations["element"] == "3He_trit"
        ].iloc[0]
        assert helium_observation["unit"] == "TU_equivalent"
        assert helium_observation["error"] == pytest.approx(0.5)


def test_h3_remains_three_observables(prepared_holten_case):
    observations = _local_4bin_observations(
        prepared_holten_case,
        prepared_holten_case.context.selected_wells[0],
    )

    assert observations["element"].tolist() == ["3H", "kr85", "39Ar"]
