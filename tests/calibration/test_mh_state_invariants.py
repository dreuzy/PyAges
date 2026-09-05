# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regression tests for committed and candidate MH state separation."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.mh._sampler_target import MHTarget
from pyages.calibration.methods.mh.sampler import _MHState
from pyages.calibration.problem import CalibrationProblem
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm


class _RejectRng:
    @staticmethod
    def random() -> float:
        return 1.0


def _problem() -> CalibrationProblem:
    model = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(model, return_type="concentrations")
    observations.set_relative_errors(0.01)
    return CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()


def _prepared_sampler(problem: CalibrationProblem, config: MHConfig):
    sampler = MetropolisHastings(config)
    sampler._bind_problem(problem)  # noqa: SLF001
    sampler.prior.load(problem.lpm)
    sampler._target = MHTarget(  # noqa: SLF001
        problem,
        sampler.prior,
        likelihood=config.likelihood,
    )
    sampler._proposal = SimpleNamespace(  # noqa: SLF001
        log_hastings_ratio=lambda _current, _candidate: 0.0
    )
    return sampler


def test_rejected_candidate_never_changes_committed_lpm(monkeypatch) -> None:
    problem = _problem()
    sampler = _prepared_sampler(
        problem,
        MHConfig(prior_option=False, likelihood=True),
    )
    observed, errors = problem.prepared_observation_arrays()
    current = problem.lpm.get_parameters_to_array()
    log_p, chi_square, concentrations = sampler._log_posterior_eval(  # noqa: SLF001
        current,
        observed,
        errors,
    )
    monkeypatch.setattr(sampler, "_draw_proposal", lambda *_args: [90.0])

    selected = sampler._mcmc_step(  # noqa: SLF001
        _MHState(current, log_p, chi_square, concentrations),
        observed,
        errors,
        _RejectRng(),
    )

    state, accepted = selected
    assert accepted is False
    assert state.params == current
    assert problem.lpm.get_parameters_to_array() == current
    assert sampler._target.candidate_lpm.get_parameters_to_array() == [90.0]  # noqa: SLF001


def test_prior_only_accepted_candidate_is_committed(monkeypatch) -> None:
    problem = _problem()
    sampler = _prepared_sampler(
        problem,
        MHConfig(prior_option=False, likelihood=False),
    )
    observed, errors = problem.prepared_observation_arrays()
    current = problem.lpm.get_parameters_to_array()
    monkeypatch.setattr(sampler, "_draw_proposal", lambda *_args: [20.0])

    selected = sampler._mcmc_step(  # noqa: SLF001
        _MHState(current, 0.0, 0.0, [np.nan]),
        observed,
        errors,
        np.random.default_rng(123),
    )

    state, accepted = selected
    assert accepted is True
    assert state.params == [20.0]
    assert problem.lpm.get_parameters_to_array() == [20.0]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"likelihood": "false"}, "likelihood must be a boolean"),
        ({"prior_option": 1}, "prior_option must be a boolean"),
        ({"componentwise_fraction": True}, "componentwise_fraction"),
        ({"seed": -1}, "non-negative integer"),
    ],
)
def test_mh_config_rejects_ambiguous_controls(kwargs, message) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        MHConfig(**kwargs)
