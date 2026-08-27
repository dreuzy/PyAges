# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Change-of-measure checks for the targeted Ploemeur benchmark prior."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pyages.calibration.ig_parameterization import (
    physical_moments_to_scipy,
    scipy_to_physical_abs_det_jacobian,
    scipy_to_physical_moments,
)
from sites.ploemeur.benchmarks.scipy_ig_prior import logpdf


def test_physical_mapping_roundtrip_and_analytic_jacobian():
    shape, scale = 12.5, 7.25
    mean, std = scipy_to_physical_moments(shape, scale)
    assert physical_moments_to_scipy(mean, std) == pytest.approx((shape, scale))

    analytic = scipy_to_physical_abs_det_jacobian(shape, scale)
    epsilon = 1.0e-5
    d_shape = (
        np.asarray(scipy_to_physical_moments(shape + epsilon, scale))
        - np.asarray(scipy_to_physical_moments(shape - epsilon, scale))
    ) / (2.0 * epsilon)
    d_scale = (
        np.asarray(scipy_to_physical_moments(shape, scale + epsilon))
        - np.asarray(scipy_to_physical_moments(shape, scale - epsilon))
    ) / (2.0 * epsilon)
    numeric = abs(float(np.linalg.det(np.column_stack((d_shape, d_scale)))))
    assert analytic == pytest.approx(std / 2.0)
    assert numeric == pytest.approx(analytic, rel=2.0e-9)


def test_named_prior_is_two_over_s_on_exact_article_support():
    first = (*scipy_to_physical_moments(1.0, 2.0), 10.0)
    second = (*scipy_to_physical_moments(4.0, 2.0), 10.0)
    log_first = logpdf(first)
    log_second = logpdf(second)
    assert log_first - log_second == pytest.approx(math.log(second[1] / first[1]))

    normalized = logpdf(first, normalized=True)
    article_volume = (100.0 - 0.1) * (30.0 - 0.1) * (50.0 - 0.1)
    assert math.exp(normalized) == pytest.approx(2.0 / (first[1] * article_volume))


@pytest.mark.parametrize(
    "shape, scale, shift",
    [
        (0.099, 1.0, 10.0),
        (100.001, 1.0, 10.0),
        (1.0, 0.099, 10.0),
        (1.0, 30.001, 10.0),
        (1.0, 1.0, 0.099),
        (1.0, 1.0, 50.001),
    ],
)
def test_named_prior_is_minus_infinity_outside_support(shape, scale, shift):
    params = (*scipy_to_physical_moments(shape, scale), shift)
    assert logpdf(params) == -math.inf
