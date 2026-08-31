# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Targeted tests for fixed Metropolis--Hastings proposals."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import multivariate_normal

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.mh.ig_coordinates import (
    physical_to_scipy_coordinates,
    scipy_to_physical_coordinates,
)
from pyages.calibration.methods.mh.proposals import (
    ComponentwiseRandomWalk,
    GaussianRandomWalk,
    native_to_sum_difference,
    regularize_empirical_covariance,
    sum_difference_inverse_jacobian,
    sum_difference_log_abs_det_jacobian,
    sum_difference_to_native,
)


class _BoundedTarget:
    p = {"mu": 10.0, "shift": 10.0}

    @staticmethod
    def param_within_bounds_array(values):
        return 0.1 <= values[0] <= 70.0 and 0.0 <= values[1] <= 70.0


def test_componentwise_proposal_uses_the_seeded_scalar_draw_protocol():
    sampler = MetropolisHastings(config=MHConfig(prior_option=False, likelihood=True))
    proposal = ComponentwiseRandomWalk("bounds", 0.1)
    proposal.names = ("mu", "shift")
    proposal.steps = np.array([1.5, 2.0])
    sampler._proposal = proposal  # noqa: SLF001
    actual_rng = np.random.default_rng(2468)
    expected_rng = np.random.default_rng(2468)
    current = [10.0, 30.0]

    actual = sampler._draw_proposal(current, actual_rng)  # noqa: SLF001
    expected = [
        current[0] + 1.5 * expected_rng.standard_normal(),
        current[1] + 2.0 * expected_rng.standard_normal(),
    ]

    assert actual == expected


def test_sum_difference_roundtrip_and_constant_jacobian():
    points = ([10.0, 30.0], [0.1, 0.0], [70.0, 70.0])
    for point in points:
        assert np.allclose(
            sum_difference_to_native(native_to_sum_difference(point)), point
        )
    jacobian = sum_difference_inverse_jacobian()
    assert abs(np.linalg.det(jacobian)) == 0.5
    assert sum_difference_log_abs_det_jacobian() == -math.log(2.0)


def test_correlated_proposal_has_requested_covariance_and_is_symmetric():
    covariance = np.array([[4.0, -1.5], [-1.5, 2.0]])
    proposal = GaussianRandomWalk(covariance)
    rng = np.random.default_rng(4381)
    current = np.array([10.0, 30.0])
    increments = np.array(
        [proposal.draw(current, rng) - current for _ in range(60_000)]
    )
    assert np.allclose(
        np.cov(increments, rowvar=False), covariance, rtol=0.035, atol=0.035
    )

    proposed = np.array([12.0, 27.0])
    forward = multivariate_normal.logpdf(proposed, mean=current, cov=covariance)
    reverse = multivariate_normal.logpdf(current, mean=proposed, cov=covariance)
    assert forward == reverse
    assert proposal.log_hastings_ratio(current, proposed) == 0.0


def test_correlated_proposal_owns_a_read_only_covariance_snapshot() -> None:
    covariance = np.array([[4.0, -1.5], [-1.5, 2.0]])
    proposal = GaussianRandomWalk(covariance)

    covariance[0, 0] = 99.0

    assert proposal.covariance[0, 0] == 4.0
    assert not proposal.covariance.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        proposal.covariance[0, 0] = 3.0
    with pytest.raises(ValueError, match="cannot set WRITEABLE flag"):
        proposal.covariance.setflags(write=True)


def test_proposal_is_reproducible_for_a_fixed_seed():
    proposal = GaussianRandomWalk.diagonal((2.0, 5.0), "sum_difference")
    first = np.random.default_rng(9012)
    second = np.random.default_rng(9012)
    draws_a = [proposal.draw((10.0, 30.0), first) for _ in range(20)]
    draws_b = [proposal.draw((10.0, 30.0), second) for _ in range(20)]
    assert np.array_equal(draws_a, draws_b)


def test_regularized_empirical_covariance_is_positive_definite():
    samples = np.column_stack((np.arange(20.0), 2.0 * np.arange(20.0)))
    covariance = regularize_empirical_covariance(samples, relative_ridge=1.0e-6)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)


def test_scipy_ig_proposal_roundtrip_and_hastings_jacobian():
    current = np.array([2400.0, 21000.0, 34.0])
    assert scipy_to_physical_coordinates(
        physical_to_scipy_coordinates(current)
    ) == pytest.approx(current)
    proposal = GaussianRandomWalk(np.eye(3), coordinate_system="scipy_ig")
    proposed = np.array([2000.0, 16000.0, 33.5])
    assert proposal.log_hastings_ratio(current, proposed) == pytest.approx(
        math.log(proposed[1] / current[1])
    )


def test_target_and_bounds_do_not_depend_on_proposal_choice():
    componentwise = MetropolisHastings(
        config=MHConfig(prior_option=False, likelihood=True)
    )
    transformed = MetropolisHastings(
        config=MHConfig(
            prior_option=False,
            likelihood=True,
            proposal_kind="sum_difference",
            proposal_scales=(2.0, 5.0),
        )
    )
    for sampler in (componentwise, transformed):

        def objective_function(params, *_args, return_concentrations=False, **_kwargs):
            result = float(params[0] ** 2 + 0.5 * params[1] ** 2)
            return (result, [1.0]) if return_concentrations else result

        problem = SimpleNamespace(
            lpm=_BoundedTarget(),
            objective_function=objective_function,
            ensure_prepared=lambda: None,
        )
        sampler._bind_problem(problem)
    args = ([10.0, 30.0], np.array([1.0]), np.array([1.0]))
    componentwise_target = componentwise._log_posterior_eval(*args)  # noqa: SLF001
    transformed_target = transformed._log_posterior_eval(*args)  # noqa: SLF001
    assert transformed_target == componentwise_target

    transformed._proposal = GaussianRandomWalk.diagonal((100.0, 100.0))
    rng = np.random.default_rng(772)
    state = [10.0, 30.0]
    log_p, objective, concentration = transformed_target
    for _ in range(500):
        state, log_p, objective, concentration, _ = transformed._mcmc_step(  # noqa: SLF001
            state,
            log_p,
            objective,
            concentration,
            np.array([1.0]),
            np.array([1.0]),
            rng,
        )
        assert _BoundedTarget.param_within_bounds_array(state)
