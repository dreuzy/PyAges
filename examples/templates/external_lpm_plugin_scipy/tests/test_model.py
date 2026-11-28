# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1

"""Scientific smoke tests for the complete SciPy-backed plugin example."""

import numpy as np
import pytest
from pyages_lpm_gamma_mean.model import GammaMeanLpm, definition


def test_gamma_mean_exact_moments_and_quantile() -> None:
    """Verify SciPy conversion through independent gamma identities.

    With ``mu=10`` and ``shape=2``, the exact standard deviation is
    ``mu / sqrt(shape)``. A 0.75 quantile round trip additionally checks that
    the same shape and scale reach both SciPy CDF and inverse-CDF operations.
    """
    model = GammaMeanLpm(directory_lpm=definition.parameter_directory)

    assert model.mean() == pytest.approx(10.0)
    assert model.std() == pytest.approx(10.0 / np.sqrt(2.0))
    assert model.cdf(model.cdf_inv(0.75)) == pytest.approx(0.75)


def test_partial_moment_converges_to_the_mean() -> None:
    """Check both limiting identities of the convolution partial moment.

    At zero, cumulative mass and partial moment vanish. At an age far into the
    gamma tail, cumulative mass approaches one and the unnormalized partial
    first moment approaches the exact full mean.
    """
    model = GammaMeanLpm(directory_lpm=definition.parameter_directory)
    cdf, moment = model.cdf_and_partial_first_moment(np.array([0.0, 1000.0]))

    np.testing.assert_allclose(cdf, [0.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(moment, [0.0, model.mean()], atol=1e-12)
