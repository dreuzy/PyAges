# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

import numpy as np
from scipy.special import expit

from examples.natural.holten.holten_reproduction import _fractions
from scripts.article.run_holten_prior_robustness import (
    LOG_DIRICHLET_NORMALIZATION,
    _fractions_to_z,
    _numerical_jacobian,
    log_abs_stick_breaking_jacobian,
    log_dirichlet1_density_in_z,
)


def test_stick_breaking_log_jacobian_matches_finite_differences() -> None:
    points = np.array([[0.0, 0.0, 0.0], [-3.1, 1.2, 2.7], [4.0, -2.0, 0.3]])
    for point in points:
        numerical = abs(np.linalg.det(_numerical_jacobian(point)))
        analytical = np.exp(log_abs_stick_breaking_jacobian(point))
        np.testing.assert_allclose(numerical, analytical, rtol=1e-7)


def test_analytical_jacobian_formula() -> None:
    point = np.array([0.4, -1.2, 2.3])
    v1, v2, v3 = expit(point)
    expected = v1 * v2 * v3 * (1 - v1) ** 3 * (1 - v2) ** 2 * (1 - v3)
    np.testing.assert_allclose(np.exp(log_abs_stick_breaking_jacobian(point)), expected)
    np.testing.assert_allclose(
        log_dirichlet1_density_in_z(point),
        np.log(expected) + LOG_DIRICHLET_NORMALIZATION,
    )


def test_fraction_to_z_round_trip() -> None:
    fractions = np.array([[0.25, 0.25, 0.25, 0.25], [0.7, 0.1, 0.15, 0.05]])
    recovered = np.apply_along_axis(_fractions, 1, _fractions_to_z(fractions))
    np.testing.assert_allclose(recovered, fractions)
