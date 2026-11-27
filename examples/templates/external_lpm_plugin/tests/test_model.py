"""Independent mathematical checks for the bounded-power example."""

from pathlib import Path

import numpy as np
import pyages_lpm_bounded_power
import pytest
from pyages_lpm_bounded_power.model import BoundedPowerLpm

DATA_ROOT = Path(pyages_lpm_bounded_power.__file__).parent / "data_lpm"


def build_model(*, tau: float = 50.0, alpha: float = 2.0) -> BoundedPowerLpm:
    """Construct the model with its packaged parameter metadata."""
    return BoundedPowerLpm(
        tau=tau,
        alpha=alpha,
        directory_lpm=DATA_ROOT,
    )


def test_pdf_is_normalized() -> None:
    model = build_model()
    ages = np.linspace(0.0, model.p["tau"], 20_001)
    integral = np.trapezoid(model.pdf(ages), ages)
    assert integral == pytest.approx(1.0, abs=1.0e-8)


def test_cdf_and_inverse_are_consistent() -> None:
    model = build_model(tau=80.0, alpha=3.0)
    probabilities = np.array([0.0, 0.1, 0.5, 0.9, 1.0])
    ages = model.cdf_inv(probabilities)
    assert model.cdf(ages) == pytest.approx(probabilities)


def test_analytical_moments_match_numerical_integration() -> None:
    model = build_model(tau=60.0, alpha=1.5)
    ages = np.linspace(0.0, model.p["tau"], 30_001)
    density = model.pdf(ages)
    numerical_mean = np.trapezoid(ages * density, ages)
    numerical_second_moment = np.trapezoid(ages**2 * density, ages)
    numerical_std = np.sqrt(numerical_second_moment - numerical_mean**2)

    assert model.mean() == pytest.approx(numerical_mean, rel=1.0e-8)
    assert model.std() == pytest.approx(numerical_std, rel=1.0e-8)


def test_partial_first_moment_matches_quadrature() -> None:
    model = build_model(tau=50.0, alpha=2.0)
    upper = 20.0
    ages = np.linspace(0.0, upper, 20_001)
    expected = np.trapezoid(ages * model.pdf(ages), ages)
    cdf, partial_moment = model.cdf_and_partial_first_moment(upper)

    assert cdf == pytest.approx(model.cdf(upper))
    assert partial_moment == pytest.approx(expected, rel=1.0e-8)


def test_support_boundaries() -> None:
    model = build_model(tau=50.0, alpha=2.0)
    assert model.pdf([-1.0, 51.0]) == pytest.approx([0.0, 0.0])
    assert model.cdf([-1.0, 50.0, 51.0]) == pytest.approx([0.0, 1.0, 1.0])
    assert model.cdf_and_partial_first_moment(-1.0) == pytest.approx((0.0, 0.0))
    assert model.cdf_and_partial_first_moment(51.0) == pytest.approx(
        (1.0, model.mean())
    )
