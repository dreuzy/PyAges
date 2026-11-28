# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Unit contracts for configurable residual objectives and diagnostics."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from pyages.calibration.methods.mh._sampler_target import MHTarget
from pyages.calibration.objective import (
    ObjectiveSpec,
    comparison_metrics,
    scaled_residuals,
)
from tests.calibration.test_inversion import _synthetic_problem


def test_scaled_residuals_separate_absolute_relative_and_uncertainty_scales() -> None:
    observed = np.array([2.0, 4.0])
    modeled = np.array([3.0, 2.0])
    errors = np.array([0.5, 2.0])

    np.testing.assert_allclose(
        scaled_residuals(observed, modeled, errors, scale="absolute"),
        [1.0, -2.0],
    )
    np.testing.assert_allclose(
        scaled_residuals(observed, modeled, errors, scale="relative"),
        [0.5, -0.5],
    )
    np.testing.assert_allclose(
        scaled_residuals(observed, modeled, errors, scale="uncertainty"),
        [2.0, -1.0],
    )


def test_objective_spec_combines_scaling_and_l1_or_squared_l2() -> None:
    observed = [2.0, 4.0]
    modeled = [3.0, 2.0]
    errors = [0.5, 2.0]

    assert ObjectiveSpec(loss="l1", scale="absolute").evaluate(
        observed, modeled, errors
    ) == pytest.approx(3.0)
    assert ObjectiveSpec(loss="l2", scale="absolute").evaluate(
        observed, modeled, errors
    ) == pytest.approx(5.0)
    assert ObjectiveSpec.relative_l1().evaluate(
        observed, modeled, errors
    ) == pytest.approx(1.0)
    assert ObjectiveSpec.relative_l2().evaluate(
        observed, modeled, errors
    ) == pytest.approx(0.5)
    assert ObjectiveSpec.pyages_default().evaluate(
        observed, modeled, errors
    ) == pytest.approx(5.0)


def test_comparison_metrics_are_independent_of_selected_objective() -> None:
    metrics = comparison_metrics(
        [2.0, 4.0],
        [3.0, 2.0],
        [0.5, 2.0],
    )

    assert metrics == pytest.approx(
        {
            "relative_l1": 1.0,
            "mean_absolute_relative_residual": 0.5,
            "relative_l2_squared": 0.5,
            "relative_rms": 0.5,
            "maximum_absolute_relative_residual": 0.5,
            "standardized_l1": 3.0,
            "mean_absolute_standardized_residual": 1.5,
            "chi_square": 5.0,
            "normalized_residual_rms": math.sqrt(2.5),
            "maximum_absolute_standardized_residual": 2.0,
        }
    )


def test_relative_floor_makes_zero_observations_finite() -> None:
    residual = scaled_residuals(
        [0.0],
        [0.5],
        [1.0],
        scale="relative",
        relative_floor=0.25,
    )

    np.testing.assert_allclose(residual, [2.0])


def test_scalar_uncertainty_is_broadcast_to_every_observation() -> None:
    residual = scaled_residuals(
        [1.0, 2.0],
        [2.0, 4.0],
        0.5,
        scale="uncertainty",
    )

    np.testing.assert_allclose(residual, [2.0, 4.0])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"loss": "unknown"}, "loss"),
        ({"scale": "unknown"}, "scale"),
        ({"relative_floor": 0.0}, "relative_floor"),
        ({"relative_floor": math.inf}, "relative_floor"),
        ({"relative_floor": "invalid"}, "relative_floor"),
        ({"relative_floor": True}, "relative_floor"),
    ],
)
def test_objective_spec_rejects_unknown_or_nonfinite_controls(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        ObjectiveSpec(**kwargs)


def test_residual_validation_rejects_invalid_scientific_arrays() -> None:
    with pytest.raises(ValueError, match="Unknown residual scale"):
        scaled_residuals([1.0], [1.0], [1.0], scale="unknown")
    with pytest.raises(ValueError, match="same shape"):
        ObjectiveSpec.pyages_default().evaluate([1.0], [1.0, 2.0], [1.0])
    with pytest.raises(ValueError, match="one-dimensional"):
        ObjectiveSpec.pyages_default().evaluate([[1.0]], [[1.0]], [[1.0]])
    with pytest.raises(ValueError, match="at least one"):
        ObjectiveSpec.pyages_default().evaluate([], [], [])
    with pytest.raises(ValueError, match="finite"):
        ObjectiveSpec.pyages_default().evaluate([1.0], [np.nan], [1.0])
    with pytest.raises(ValueError, match="strictly positive"):
        ObjectiveSpec.pyages_default().evaluate([1.0], [1.0], [0.0])


def test_mh_target_remains_gaussian_chi_square_and_ignores_objective_spec(
    monkeypatch,
) -> None:
    problem = _synthetic_problem()
    observed, errors = problem.prepared_observation_arrays()
    parameters = problem.lpm.get_parameters_to_array()
    expected_chi_square = problem.objective_function(
        parameters,
        observed,
        errors,
    )
    monkeypatch.setattr(
        ObjectiveSpec,
        "evaluate",
        lambda *_args, **_kwargs: pytest.fail(
            "MH must not evaluate the configurable deterministic objective"
        ),
    )

    target = MHTarget(problem, SimpleNamespace(option=False), likelihood=True)
    log_target, chi_square, modeled = target.evaluate(parameters, observed, errors)

    assert chi_square == pytest.approx(expected_chi_square)
    assert log_target == pytest.approx(-0.5 * expected_chi_square)
    assert len(modeled) == len(observed)
