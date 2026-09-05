# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for optional explicit Metropolis-Hastings initial parameters."""

from types import SimpleNamespace

import numpy as np
import pytest

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.mh._sampler_target import MHTarget


class _FakeLpm:
    def __init__(self):
        self.p = {"mu": 10.0, "shift": 10.0}

    def get_calibration_range(self, name):
        return {"mu": (0.1, 70.0), "shift": (0.0, 70.0)}[name]

    def get_calibration_ranges(self):
        return {name: self.get_calibration_range(name) for name in self.p}

    def param_within_calibration_range_array(self, values):
        return all(
            self.get_calibration_range(name)[0]
            <= value
            <= self.get_calibration_range(name)[1]
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
    mh._target = MHTarget(problem, mh.prior, likelihood=False)  # noqa: SLF001
    state = mh._initialize_state(  # noqa: SLF001
        np.array([]), np.array([])
    )
    return mh, state.params


def test_explicit_initial_params_are_applied_without_prior():
    mh, params = _initialize({"mu": 35.0, "shift": 20.0})

    assert params == [35.0, 20.0]
    payload = mh._parameters_payload()  # noqa: SLF001
    assert payload["initialization_source"] == "config"
    assert payload["initial_mu"] == 35.0
    assert payload["initial_shift"] == 20.0


def test_initial_params_are_optional_and_keep_lpm_defaults():
    mh, params = _initialize(None)

    assert params == [10.0, 10.0]
    payload = mh._parameters_payload()  # noqa: SLF001
    assert payload["initialization_source"] == "lpm_default"


@pytest.mark.parametrize(
    "initial_params, message",
    [
        ({"mu": 35.0}, "must define exactly"),
        ({"mu": 35.0, "shift": 20.0, "other": 1.0}, "must define exactly"),
        ({"mu": 80.0, "shift": 20.0}, "outside the LPM calibration ranges"),
    ],
)
def test_invalid_initial_params_are_rejected(initial_params, message):
    with pytest.raises(ValueError, match=message):
        _initialize(initial_params)
