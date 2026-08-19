"""Analytical tests for discrete two-mass LPM distributions."""

import numpy as np
import pytest

from pyage.lpm.models.dirac import DiracLpm
from pyage.lpm.models.dirac_double import DiracDoubleLpm
from pyage.lpm.models.dirac_double_1_set import DiracDouble1SetLpm
from pyage.lpm.models.mix_exponential_shifted import MixExponentialShiftedLpm
from tests.utils import paths as test_paths


def _data_directory() -> str:
    return str(test_paths.lpm_data_dir())


def test_dirac_cdf_is_scalar_safe_and_right_continuous():
    model = DiracLpm(mu=10.0, directory_lpm=_data_directory())

    assert model.cdf(9.999) == pytest.approx(0.0)
    assert model.cdf(10.0) == pytest.approx(1.0)
    assert model.cdf(10.001) == pytest.approx(1.0)


def test_dirac_double_cdf_includes_each_point_mass():
    model = DiracDoubleLpm(
        mu1=10.0, mu2=5.0, rate=0.2, directory_lpm=_data_directory()
    )

    values = model.cdf(np.array([9.999, 10.0, 14.999, 15.0]))

    assert values == pytest.approx([0.0, 0.2, 0.2, 1.0])


@pytest.mark.parametrize(
    ("probability", "expected"),
    [(0.0, 10.0), (0.2, 10.0), (0.200001, 15.0), (0.9, 15.0)],
)
def test_dirac_double_generalized_quantile(probability, expected):
    model = DiracDoubleLpm(
        mu1=10.0, mu2=5.0, rate=0.2, directory_lpm=_data_directory()
    )

    assert model.cdf_inv(probability) == pytest.approx(expected)


def test_dirac_double_1_set_cdf_and_generalized_quantile():
    model = DiracDouble1SetLpm(
        mufree=10.0, muset=70.0, rate=0.3, directory_lpm=_data_directory()
    )

    values = model.cdf(np.array([9.999, 10.0, 69.999, 70.0]))

    assert values == pytest.approx([0.0, 0.3, 0.3, 1.0])
    assert model.cdf_inv(0.0) == pytest.approx(10.0)
    assert model.cdf_inv(0.3) == pytest.approx(10.0)
    assert model.cdf_inv(0.300001) == pytest.approx(70.0)


@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_dirac_double_1_set_degenerate_distribution_has_zero_std(rate):
    model = DiracDouble1SetLpm(
        mufree=10.0, muset=70.0, rate=rate, directory_lpm=_data_directory()
    )

    assert model.std() == pytest.approx(0.0)


def _mixed_model(rate: float = 0.3) -> MixExponentialShiftedLpm:
    return MixExponentialShiftedLpm(
        rate=rate,
        mu1=10.0,
        mu2=8.0,
        shift=5.0,
        directory_lpm=_data_directory(),
    )


def test_mixed_cdf_is_scalar_safe_and_includes_the_dirac_mass():
    model = _mixed_model()

    assert model.cdf(9.999) == pytest.approx(0.0)
    assert model.cdf(10.0) == pytest.approx(0.3)
    assert model.cdf(14.999) == pytest.approx(0.3)
    assert model.cdf(15.0) == pytest.approx(0.3)
    assert model.cdf(30.0) == pytest.approx(
        0.3 + 0.7 * (1.0 - np.exp(-(30.0 - 15.0) / 8.0))
    )


@pytest.mark.parametrize("probability", [0.0, 0.1, 0.3, 0.300001, 0.5, 0.9, 0.999])
def test_mixed_generalized_quantile(probability):
    model = _mixed_model()
    expected = (
        10.0
        if probability <= 0.3
        else 15.0 - 8.0 * np.log((1.0 - probability) / 0.7)
    )

    assert model.cdf_inv(probability) == pytest.approx(expected)


def test_mixed_generalized_quantile_handles_degenerate_rates():
    continuous = _mixed_model(rate=0.0)
    discrete = _mixed_model(rate=1.0)

    assert continuous.cdf_inv(0.0) == pytest.approx(15.0)
    assert continuous.cdf_inv(0.5) == pytest.approx(15.0 + 8.0 * np.log(2.0))
    assert discrete.cdf_inv(0.0) == pytest.approx(10.0)
    assert discrete.cdf_inv(1.0) == pytest.approx(10.0)


def test_mixed_moments_include_both_component_locations_and_tail_variance():
    model = _mixed_model()
    expected_mean = 0.3 * 10.0 + 0.7 * (15.0 + 8.0)
    expected_variance = (
        0.3 * (10.0 - expected_mean) ** 2
        + 0.7 * (8.0**2 + (15.0 + 8.0 - expected_mean) ** 2)
    )

    assert model.mean() == pytest.approx(expected_mean)
    assert model.std() == pytest.approx(np.sqrt(expected_variance))
