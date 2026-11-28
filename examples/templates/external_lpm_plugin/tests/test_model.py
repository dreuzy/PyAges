# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1

"""Scientific smoke tests for the complete external-plugin example."""

import numpy as np
import pytest
from pyages_lpm_bounded_power.model import BoundedPowerLpm, definition


def test_bounded_power_closed_form_values() -> None:
    """Compare implementation results with independent closed-form identities.

    The default ``alpha=2`` and ``maximum_age=50`` give simple exact CDF,
    quantile, mean, and variance values that exercise every ordinary
    probability method without relying on numerical integration.
    """
    model = BoundedPowerLpm(directory_lpm=definition.parameter_directory)

    assert model.cdf(25.0) == pytest.approx(0.25)
    assert model.cdf_inv(0.25) == pytest.approx(25.0)
    assert model.mean() == pytest.approx(100.0 / 3.0)
    assert model.std() == pytest.approx(np.sqrt(1250.0 / 9.0))


def test_partial_moment_converges_to_the_mean() -> None:
    """Check the convolution primitive at both finite support boundaries.

    Cumulative mass and partial moment must start at zero. At ``maximum_age``,
    all probability mass is included and the raw partial moment must equal the
    independently evaluated full mean.
    """
    model = BoundedPowerLpm(directory_lpm=definition.parameter_directory)
    cdf, moment = model.cdf_and_partial_first_moment(np.array([0.0, 50.0]))

    np.testing.assert_allclose(cdf, [0.0, 1.0])
    np.testing.assert_allclose(moment, [0.0, model.mean()])
