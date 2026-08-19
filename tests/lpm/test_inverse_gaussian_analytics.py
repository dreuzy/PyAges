"""Analytical contract tests for inverse-Gaussian LPM parameterization."""

import numpy as np
import pytest
from scipy.integrate import quad

from pyage.lpm.lpm_build import lpm_build
from pyage.lpm.models.inverse_gaussian import InverseGaussianLpm
from pyage.lpm.models.inverse_gaussian_shifted import InverseGaussianShiftedLpm
from tests.utils import paths as test_paths


PARAMETER_PAIRS = [
    (1.0, 1.0),
    (10.0, 20.0),
    (20.0, 10.0),
    (30.0, 20.0),
    (40.0, 1.0),
    (1.0, 40.0),
]
QUANTILES = np.array([0.01, 0.1, 0.5, 0.9, 0.99])


def _data_directory() -> str:
    return str(test_paths.lpm_data_dir())


def _factory_model(mean_age: float, std_age: float) -> InverseGaussianLpm:
    """Build through the public registry/factory and apply [mu, sigma]."""
    model = lpm_build("ig", directory_lpm=_data_directory())
    model.set_param_from_array([mean_age, std_age])
    assert model.get_parameters_to_array() == [mean_age, std_age]
    return model


@pytest.mark.parametrize("mean_age,std_age", PARAMETER_PAIRS)
def test_inverse_gaussian_parameters_are_physical_moments(mean_age, std_age):
    model = _factory_model(mean_age, std_age)

    assert model.mean() == pytest.approx(mean_age, rel=1e-12)
    assert model.std() == pytest.approx(std_age, rel=1e-12)
    assert model.moments()[:2] == pytest.approx([mean_age, std_age], rel=1e-12)


@pytest.mark.parametrize("mean_age,std_age", PARAMETER_PAIRS)
def test_inverse_gaussian_pdf_is_normalized(mean_age, std_age):
    model = _factory_model(mean_age, std_age)

    def density_in_log_time(log_time: float) -> float:
        time = np.exp(log_time)
        return float(model.pdf(time)) * time

    integral, integration_error = quad(
        density_in_log_time,
        -40.0,
        40.0,
        points=[np.log(mean_age)],
        epsabs=1e-12,
        epsrel=1e-12,
        limit=1000,
    )

    assert integration_error < 1e-10
    assert integral == pytest.approx(1.0, rel=1e-11, abs=1e-12)


@pytest.mark.parametrize("mean_age,std_age", PARAMETER_PAIRS)
def test_inverse_gaussian_cdf_and_ppf_are_consistent(mean_age, std_age):
    model = _factory_model(mean_age, std_age)

    ages = model.cdf_inv(QUANTILES)

    assert np.all(np.isfinite(ages))
    assert model.cdf(ages) == pytest.approx(QUANTILES, rel=1e-11, abs=1e-12)


def test_shifted_inverse_gaussian_mean_includes_shift_only_once():
    model = InverseGaussianShiftedLpm(
        mu=10.0, sigma=2.0, shift=5.0, directory_lpm=_data_directory()
    )

    assert model.mean() == pytest.approx(15.0)
    assert model.std() == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("model", "upper"),
    [
        (InverseGaussianLpm(10.0, 2.0, _data_directory()), 12.0),
        (InverseGaussianShiftedLpm(10.0, 2.0, 5.0, _data_directory()), 17.0),
    ],
)
def test_inverse_gaussian_partial_first_moment_matches_quad(model, upper):
    cdf, partial_moment = model.cdf_and_partial_first_moment(upper)
    reference = quad(
        lambda age: age * float(model.pdf(age)),
        0.0,
        upper,
        epsabs=1e-12,
        epsrel=1e-12,
        limit=1000,
    )[0]

    assert cdf == pytest.approx(model.cdf(upper), rel=1e-13, abs=1e-14)
    assert partial_moment == pytest.approx(reference, rel=1e-12, abs=1e-13)


def test_inverse_gaussian_matches_article_density():
    mean_age, std_age = 10.0, 2.0
    model = InverseGaussianLpm(
        mu=mean_age, sigma=std_age, directory_lpm=_data_directory()
    )
    ages = np.array([1.0, 5.0, 10.0, 20.0])
    expected = (
        mean_age ** 1.5
        / np.sqrt(2.0 * np.pi * std_age**2 * ages**3)
        * np.exp(-mean_age * (ages - mean_age) ** 2 / (2.0 * std_age**2 * ages))
    )

    assert model.pdf(ages) == pytest.approx(expected, rel=1e-12, abs=1e-15)


@pytest.mark.parametrize("mean_age,std_age", [(0.0, 1.0), (-1.0, 1.0), (1.0, 0.0), (1.0, -1.0)])
def test_inverse_gaussian_rejects_non_positive_moments(mean_age, std_age):
    model = InverseGaussianLpm(
        mu=mean_age, sigma=std_age, directory_lpm=_data_directory()
    )

    with pytest.raises(ValueError):
        model.mean()
