# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for reproducible MH ensemble configuration and initialization."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from scipy.stats import truncnorm

from pyages.calibration.methods.mh import ensemble_config
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
    build_seed_plan,
)
from pyages.calibration.methods.mh.initialization import build_initial_states
from pyages.calibration.methods.mh.prior import Prior


class _TwoParameterModel:
    def __init__(self) -> None:
        self.p = {"mu": 4.0, "width": 3.0}

    def get_param_names(self):
        return list(self.p)

    def get_parameters_to_array(self):
        return list(self.p.values())

    def get_p_min(self, name):
        return {"mu": 0.0, "width": 1.0}[name]

    def get_p_max(self, name):
        return {"mu": 10.0, "width": 9.0}[name]


def _parametric_prior() -> Prior:
    prior = Prior(option=True, typ="parametric")
    prior.distributions = {"mu": "normal", "width": "uniform"}
    prior.parameters = {"mu": [12.0, 2.0], "width": [2.0, 8.0]}
    return prior


@pytest.mark.parametrize("chains", [True, 1, 0, -2, 2.5])
def test_ensemble_config_requires_at_least_two_integer_chains(chains) -> None:
    with pytest.raises(ValueError, match="chains"):
        MHEnsembleConfig(chains=chains)


@pytest.mark.parametrize("seed", [True, -1, 1.5, "12"])
def test_ensemble_config_rejects_invalid_master_seed(seed) -> None:
    with pytest.raises(ValueError, match="master_seed"):
        MHEnsembleConfig(master_seed=seed)


def test_omitted_master_seed_is_realized_and_recorded(monkeypatch) -> None:
    monkeypatch.setattr(ensemble_config.secrets, "randbits", lambda bits: 987_654)

    config = MHEnsembleConfig(master_seed=None)
    plan = build_seed_plan(config)

    assert config.master_seed == 987_654
    assert plan.master_seed == 987_654


def test_seed_plan_is_reproducible_distinct_and_phase_separated() -> None:
    config = MHEnsembleConfig(chains=4, master_seed=20260830)

    first = build_seed_plan(config)
    second = build_seed_plan(config)
    all_seeds = first.initialization_seeds + first.pilot_seeds + first.production_seeds

    assert first == second
    assert first.chain_count == 4
    assert len(set(all_seeds)) == 12
    assert first.initialization_seeds != first.production_seeds


def test_configuration_objects_are_frozen() -> None:
    config = MHEnsembleConfig()

    assert config.initialization.strategy == "bounds_stratified"
    with pytest.raises(FrozenInstanceError):
        config.chains = 8


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: MHInitializationConfig(strategy="random"), "strategy"),
        (lambda: MHInitializationConfig(max_attempts=0), "max_attempts"),
        (lambda: MHPilotConfig(burn_in=1.0), "burn_in"),
        (lambda: MHPilotConfig(nstep=4, burn_in=0.5), "two covariance draws"),
        (lambda: MHPilotConfig(relative_ridge=-1.0), "relative_ridge"),
        (lambda: MHDiagnosticsConfig(max_rhat=0.99), "max_rhat"),
        (lambda: MHDiagnosticsConfig(min_tail_ess=0.0), "min_tail_ess"),
    ],
)
def test_nested_configuration_rejects_invalid_controls(factory, message) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_explicit_starts_are_defensively_copied_and_length_checked() -> None:
    original = {"mu": 2.0, "width": 3.0}
    config = MHInitializationConfig(
        strategy="explicit",
        explicit_starts=(original,),
    )
    original["mu"] = 9.0

    assert config.explicit_starts is not None
    assert config.explicit_starts[0]["mu"] == 2.0
    with pytest.raises(TypeError):
        config.explicit_starts[0]["mu"] = 4.0
    with pytest.raises(ValueError, match="one state per chain"):
        build_initial_states(_TwoParameterModel(), None, config, 2, (1, 2))


def test_explicit_starts_return_fresh_ordered_dictionaries() -> None:
    starts = ({"width": 3.0, "mu": 2.0}, {"mu": 8.0, "width": 7.0})
    config = MHInitializationConfig(strategy="explicit", explicit_starts=starts)

    states = build_initial_states(_TwoParameterModel(), None, config, 2, (101, 102))

    assert states == ({"mu": 2.0, "width": 3.0}, {"mu": 8.0, "width": 7.0})
    assert list(states[0]) == ["mu", "width"]
    assert states[0] is not starts[0]


@pytest.mark.parametrize(
    ("state", "message"),
    [
        ({"mu": 2.0}, "exactly"),
        ({"mu": np.nan, "width": 3.0}, "finite"),
        ({"mu": 11.0, "width": 3.0}, "outside"),
    ],
)
def test_explicit_starts_must_be_complete_finite_and_bounded(state, message) -> None:
    config = MHInitializationConfig(
        strategy="explicit", explicit_starts=(state, dict(state))
    )

    with pytest.raises(ValueError, match=message):
        build_initial_states(_TwoParameterModel(), None, config, 2, (1, 2))


def test_model_defaults_are_copied_without_mutating_the_lpm() -> None:
    lpm = _TwoParameterModel()
    config = MHInitializationConfig(strategy="model_default")

    states = build_initial_states(lpm, None, config, 3, (1, 2, 3))
    states[0]["mu"] = 8.0

    assert lpm.p == {"mu": 4.0, "width": 3.0}
    assert states[1] == {"mu": 4.0, "width": 3.0}


def test_prior_sampling_is_reproducible_bounded_and_does_not_clip_normals() -> None:
    lpm = _TwoParameterModel()
    prior = _parametric_prior()
    config = MHInitializationConfig(strategy="prior_sample")
    seeds = (11, 22, 33, 44)

    first = build_initial_states(lpm, prior, config, 4, seeds)
    second = build_initial_states(lpm, prior, config, 4, seeds)

    assert first == second
    assert len({tuple(state.values()) for state in first}) == 4
    assert all(0.0 < state["mu"] < 10.0 for state in first)
    assert all(2.0 <= state["width"] < 8.0 for state in first)
    assert lpm.p == {"mu": 4.0, "width": 3.0}


def test_prior_map_uses_bounded_mode_and_common_uniform_midpoint() -> None:
    states = build_initial_states(
        _TwoParameterModel(),
        _parametric_prior(),
        MHInitializationConfig(strategy="prior_map"),
        2,
        (1, 2),
    )

    assert states == (
        {"mu": 10.0, "width": 5.0},
        {"mu": 10.0, "width": 5.0},
    )


def test_bounds_stratified_places_one_point_in_each_marginal_stratum() -> None:
    chain_count = 4
    states = build_initial_states(
        _TwoParameterModel(),
        None,
        MHInitializationConfig(strategy="bounds_stratified"),
        chain_count,
        (101, 102, 103, 104),
    )

    for name, minimum, maximum in (("mu", 0.0, 10.0), ("width", 1.0, 9.0)):
        normalized = np.asarray(
            [(state[name] - minimum) / (maximum - minimum) for state in states]
        )
        strata = np.floor(chain_count * normalized).astype(int)
        assert sorted(strata.tolist()) == list(range(chain_count))


def test_bounds_stratified_uses_effective_uniform_prior_mass() -> None:
    prior = Prior(option=True, typ="parametric")
    prior.distributions = {"mu": "uniform", "width": "uniform"}
    prior.parameters = {"mu": [4.0, 6.0], "width": [2.0, 8.0]}
    states = build_initial_states(
        _TwoParameterModel(),
        prior,
        MHInitializationConfig(strategy="bounds_stratified"),
        4,
        (10, 20, 30, 40),
    )

    for name, minimum, maximum in (("mu", 4.0, 6.0), ("width", 2.0, 8.0)):
        normalized = np.asarray(
            [(state[name] - minimum) / (maximum - minimum) for state in states]
        )
        strata = np.floor(4 * normalized).astype(int)
        assert sorted(strata.tolist()) == [0, 1, 2, 3]


def test_bounds_stratified_uses_truncated_normal_probability_strata() -> None:
    prior = _parametric_prior()
    chain_count = 4
    states = build_initial_states(
        _TwoParameterModel(),
        prior,
        MHInitializationConfig(strategy="bounds_stratified"),
        chain_count,
        (10, 20, 30, 40),
    )

    standardized_minimum = (0.0 - 12.0) / 2.0
    standardized_maximum = (10.0 - 12.0) / 2.0
    probabilities = truncnorm.cdf(
        [state["mu"] for state in states],
        standardized_minimum,
        standardized_maximum,
        loc=12.0,
        scale=2.0,
    )
    strata = np.floor(chain_count * probabilities).astype(int)
    assert sorted(strata.tolist()) == list(range(chain_count))


def test_bounds_stratified_inverts_empirical_mass_without_sampling_zero_gap() -> None:
    prior = Prior(option=True, typ="empirical")
    prior.parameters = {
        "mu": np.array([[0.0, 1.0], [2.0, 1.0], [4.0, 0.0], [6.0, 0.0], [10.0, 1.0]]),
        "width": np.array([[1.0, 1.0], [9.0, 1.0]]),
    }
    states = build_initial_states(
        _TwoParameterModel(),
        prior,
        MHInitializationConfig(strategy="bounds_stratified"),
        8,
        tuple(range(100, 108)),
    )

    assert all(not 4.0 < state["mu"] < 6.0 for state in states)
    assert all(
        math.isfinite(prior.log_evaluate(_TwoParameterModel(), list(state.values())))
        for state in states
    )


def test_bounds_stratified_rejects_empty_effective_prior_mass_immediately() -> None:
    prior = Prior(option=True, typ="parametric")
    prior.distributions = {"mu": "uniform", "width": "uniform"}
    prior.parameters = {"mu": [20.0, 30.0], "width": [2.0, 8.0]}

    with pytest.raises(ValueError, match="no positive support for mu"):
        build_initial_states(
            _TwoParameterModel(),
            prior,
            MHInitializationConfig(strategy="bounds_stratified"),
            2,
            (10, 20),
        )


def test_bounds_stratified_is_reproducible_but_changes_with_seed_plan() -> None:
    config = MHInitializationConfig(strategy="bounds_stratified")
    first = build_initial_states(_TwoParameterModel(), None, config, 3, (10, 20, 30))
    replay = build_initial_states(_TwoParameterModel(), None, config, 3, (10, 20, 30))
    changed = build_initial_states(_TwoParameterModel(), None, config, 3, (11, 21, 31))

    assert first == replay
    assert first != changed


@pytest.mark.parametrize("seeds", [(1,), (1, 1), (1, -2)])
def test_initialization_requires_one_distinct_nonnegative_seed_per_chain(seeds) -> None:
    with pytest.raises(ValueError, match="seeds"):
        build_initial_states(
            _TwoParameterModel(),
            None,
            MHInitializationConfig(strategy="model_default"),
            2,
            seeds,
        )
