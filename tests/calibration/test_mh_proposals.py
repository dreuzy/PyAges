"""Targeted tests for fixed Metropolis--Hastings proposals."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import multivariate_normal

from pyage.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyage.calibration.mh_proposals import (
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


def test_target_and_bounds_do_not_depend_on_proposal_choice():
    legacy = MetropolisHastings(config=MHConfig(prior_option=False, likelihood=True))
    transformed = MetropolisHastings(
        config=MHConfig(
            prior_option=False,
            likelihood=True,
            proposal_kind="sum_difference",
            proposal_scales=(2.0, 5.0),
        )
    )
    for sampler in (legacy, transformed):
        sampler.lpm = _BoundedTarget()
        sampler.objective_function = lambda params, *_args, **_kwargs: (
            float(params[0] ** 2 + 0.5 * params[1] ** 2),
            [1.0],
        )
    args = ([10.0, 30.0], np.array([1.0]), np.array([1.0]))
    legacy_target = legacy._MetropolisHastings__log_posterior_eval(*args)  # noqa: SLF001
    transformed_target = transformed._MetropolisHastings__log_posterior_eval(*args)  # noqa: SLF001
    assert transformed_target == legacy_target

    transformed._proposal = GaussianRandomWalk.diagonal((100.0, 100.0))
    rng = np.random.default_rng(772)
    state = [10.0, 30.0]
    log_p, objective, concentration = transformed_target
    for _ in range(500):
        state, log_p, objective, concentration, _ = (
            transformed._MetropolisHastings__mcmc_step(  # noqa: SLF001
                state,
                log_p,
                objective,
                concentration,
                np.array([1.0]),
                np.array([1.0]),
                rng,
            )
        )
        assert _BoundedTarget.param_within_bounds_array(state)
