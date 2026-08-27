# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for optional explicit Metropolis-Hastings initial parameters."""

from types import SimpleNamespace

import numpy as np
import pytest

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig


class _FakeLpm:
    def __init__(self):
        self.p = {"mu": 10.0, "shift": 10.0}

    def get_p_min(self, name):
        return {"mu": 0.1, "shift": 0.0}[name]

    def get_p_max(self, name):
        return 70.0

    def param_within_bounds_array(self, values):
        return all(
            self.get_p_min(name) <= value <= self.get_p_max(name)
            for name, value in zip(self.p, values, strict=False)
        )

    def set_param_from_array(self, values):
        self.p.update(zip(self.p, values, strict=False))

    def get_parameters_to_array(self):
        return list(self.p.values())

    def param_init(self):
        return [10.0, 10.0]


def _initialize(initial_params):
    mh = MetropolisHastings(
        config=MHConfig(
            prior_option=False,
            likelihood=False,
            initial_params=initial_params,
        )
    )
    problem = SimpleNamespace(lpm=_FakeLpm(), ensure_prepared=lambda: None)
    mh._bind_problem(problem)
    mh.proposal_step.value = {"mu": 1.5, "shift": 1.5}
    params, *_ = mh._MetropolisHastings__initialize_state(  # noqa: SLF001
        np.array([]), np.array([])
    )
    return mh, params


def test_explicit_initial_params_are_applied_without_prior():
    mh, params = _initialize({"mu": 35.0, "shift": 20.0})

    assert params == [35.0, 20.0]
    payload = mh._MetropolisHastings__parameters_payload()  # noqa: SLF001
    assert payload["initialization_source"] == "config"
    assert payload["initial_mu"] == 35.0
    assert payload["initial_shift"] == 20.0


def test_initial_params_are_optional_and_keep_lpm_defaults():
    mh, params = _initialize(None)

    assert params == [10.0, 10.0]
    payload = mh._MetropolisHastings__parameters_payload()  # noqa: SLF001
    assert payload["initialization_source"] == "lpm_default"


@pytest.mark.parametrize(
    "initial_params, message",
    [
        ({"mu": 35.0}, "must define exactly"),
        ({"mu": 35.0, "shift": 20.0, "other": 1.0}, "must define exactly"),
        ({"mu": 80.0, "shift": 20.0}, "outside the LPM bounds"),
    ],
)
def test_invalid_initial_params_are_rejected(initial_params, message):
    with pytest.raises(ValueError, match=message):
        _initialize(initial_params)
