"""Scientific invariants and independent references for convolution."""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from scipy.integrate import IntegrationWarning, quad
from scipy.stats import expon

from pyage.convolution.convolution import Convolution, ConvolutionError
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.lpm_build import lpm_build
from pyage.lpm.models.dirac_double_1_set import DiracDouble1SetLpm
from pyage.lpm.models.mix_exponential_shifted import MixExponentialShiftedLpm
from pyage.tracer.tracer_protocol import ConstantTracer, SyntheticTracer
from pyage.tracer.tracer_root import Tracer
from tests.utils import paths as test_paths


def _mixed_lpm(rate: float) -> MixExponentialShiftedLpm:
    return MixExponentialShiftedLpm(
        rate=rate,
        mu1=10.0,
        mu2=8.0,
        shift=5.0,
        directory_lpm=str(test_paths.lpm_data_dir()),
    )


@pytest.mark.parametrize("rate", [0.0, 0.1, 0.5, 0.9, 1.0])
def test_mix_dirac_exponential_conserves_mass_for_constant_tracer(rate):
    tracer = ConstantTracer(concentration=1.0, datemin=1800.0)
    lpm = _mixed_lpm(rate)

    value = Convolution(tracer, date=2010.0).convolve(lpm)

    assert value == pytest.approx(1.0, rel=2e-7, abs=2e-7)


@pytest.mark.parametrize("rate", [0.0, 0.1, 0.5, 0.9, 1.0])
def test_mix_dirac_exponential_matches_weighted_independent_reference(rate):
    tracer = SyntheticTracer(
        datemin=1800.0,
        concentration_fn=lambda date, age: 2.0 + 0.01 * np.asarray(age),
    )
    lpm = _mixed_lpm(rate)
    conv = Convolution(tracer, date=2010.0)

    continuous_reference = quad(
        lambda age: (2.0 + 0.01 * age) * lpm.continuous_pdf(age),
        lpm.p["mu1"] + lpm.p["shift"],
        np.inf,
        epsabs=1e-12,
        epsrel=1e-12,
    )[0]
    expected = rate * (2.0 + 0.01 * lpm.p["mu1"]) + (1.0 - rate) * continuous_reference

    assert conv.convolve(lpm) == pytest.approx(expected, rel=2e-7, abs=2e-7)


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("ig", {"mu": 0.5, "sigma": 0.1}),
        ("ig_shifted", {"mu": 0.5, "sigma": 0.1, "shift": 5.0}),
        ("gamma", {"k": 10.0, "scale": 0.1}),
        ("uniform", {"tmin": 5.0, "delta": 0.5}),
        ("weibull", {"k": 1.7, "lambda": 12.0}),
        ("shapefree_n_oldbin", {}),
    ],
)
def test_cdf_moment_constant_tracer_returns_exact_window_mass(name, parameters):
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update(parameters)
    conv = Convolution(tracer, date=2010.0)

    value = conv.convolve(lpm)

    assert value == pytest.approx(conv.window_mass(lpm), rel=2e-14, abs=2e-14)
    assert conv.diagnostics is not None
    assert conv.diagnostics.window_mass == pytest.approx(value)


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("exp", {"mu": 10.0}),
        ("exp_shifted", {"mu": 10.0, "shift": 5.0}),
    ],
)
def test_exponential_continuous_paths_conserve_window_mass(name, parameters):
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update(parameters)
    conv = Convolution(tracer, date=2010.0)

    assert conv.convolve(lpm) == pytest.approx(
        conv.window_mass(lpm), rel=2e-14, abs=2e-14
    )
    assert conv.diagnostics is not None


@pytest.mark.parametrize("name", ["dirac", "dirac_double", "dirac_double_1_set"])
def test_discrete_paths_conserve_mass_for_constant_tracer(name):
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))

    assert Convolution(tracer, date=2010.0).convolve(lpm) == pytest.approx(1.0)


def test_discrete_paths_omit_masses_outside_the_tracer_window():
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)

    single = lpm_build("dirac", directory_lpm=str(test_paths.lpm_data_dir()))
    single.p["mu"] = 120.0
    assert Convolution(tracer, date=2010.0).convolve(single) == 0.0

    double = lpm_build("dirac_double", directory_lpm=str(test_paths.lpm_data_dir()))
    double.p.update({"mu1": 100.0, "mu2": 20.0, "rate": 0.3})
    assert Convolution(tracer, date=2010.0).convolve(double) == pytest.approx(0.3)

    one_fixed = DiracDouble1SetLpm(
        mufree=120.0,
        muset=70.0,
        rate=0.3,
        directory_lpm=str(test_paths.lpm_data_dir()),
    )
    assert Convolution(tracer, date=2010.0).convolve(one_fixed) == pytest.approx(0.7)


def test_mixed_path_omits_both_components_when_they_are_outside_the_window():
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = MixExponentialShiftedLpm(
        rate=0.5,
        mu1=120.0,
        mu2=8.0,
        shift=5.0,
        directory_lpm=str(test_paths.lpm_data_dir()),
    )

    assert Convolution(tracer, date=2010.0).convolve(lpm) == 0.0


def test_mixed_window_mass_includes_a_dirac_at_age_zero():
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = MixExponentialShiftedLpm(
        rate=0.3,
        mu1=0.0,
        mu2=8.0,
        shift=5.0,
        directory_lpm=str(test_paths.lpm_data_dir()),
    )
    convolution = Convolution(tracer, date=2010.0)

    value = convolution.convolve(lpm)

    assert value == pytest.approx(convolution.window_mass(lpm), rel=2e-14)
    assert convolution.diagnostics.window_mass == pytest.approx(value, rel=2e-14)


@pytest.mark.parametrize(
    ("name", "mu", "shift"),
    [
        ("exp", 1000.0, 0.0),
        ("exp_shifted", 1000.0, 109.9),
        ("exp_shifted", 0.1, 109.9),
    ],
)
def test_exponential_continuous_path_preserves_strongly_truncated_mass(name, mu, shift):
    tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p["mu"] = mu
    if name == "exp_shifted":
        lpm.p["shift"] = shift
    conv = Convolution(tracer, date=2010.0)

    assert conv.convolve(lpm) == pytest.approx(
        conv.window_mass(lpm), rel=2e-14, abs=2e-14
    )


def test_continuous_path_keeps_physical_truncation_without_renormalizing():
    tracer = ConstantTracer(concentration=1.0, datemin=2000.0)
    lpm = lpm_build("gamma", directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update({"k": 0.5, "scale": 50.0})
    conv = Convolution(tracer, date=2010.0)

    value = conv.convolve(lpm)
    expected_mass = float(lpm.cdf(10.0) - lpm.cdf(0.0))

    assert 0.0 < expected_mass < 1.0
    assert value == pytest.approx(expected_mass, rel=2e-14, abs=2e-14)


def test_continuous_path_returns_real_zero_for_distribution_outside_window():
    tracer = ConstantTracer(concentration=1.0, datemin=2000.0)
    lpm = lpm_build("uniform", directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update({"tmin": 50.0, "delta": 0.5})
    conv = Convolution(tracer, date=2010.0)

    assert conv.convolve(lpm) == 0.0
    assert conv.diagnostics.window_mass == 0.0


class _CountingTracer(ConstantTracer):
    def __init__(self):
        super().__init__(concentration=1.0, datemin=1900.0)
        self.calls = 0

    def get_concentration(self, date, time):
        self.calls += 1
        ages = np.asarray(time, dtype=float)
        return 1.0 + 0.01 * ages


def test_prepare_caches_all_tracer_evaluations():
    tracer = _CountingTracer()
    lpm = lpm_build("ig", directory_lpm=str(test_paths.lpm_data_dir()))
    conv = Convolution(tracer, date=2010.0)

    grid = conv.prepare()
    calls_after_prepare = tracer.calls
    assert calls_after_prepare > 0
    assert grid.edges[0] == 0.0
    assert grid.edges[-1] == 110.0

    original_distribution_evaluation = lpm.cdf_and_partial_first_moment
    distribution_calls = 0

    def counted_distribution_evaluation(ages):
        nonlocal distribution_calls
        distribution_calls += 1
        return original_distribution_evaluation(ages)

    lpm.cdf_and_partial_first_moment = counted_distribution_evaluation

    completed = 0
    for target in (1, 10, 100):
        for index in range(completed, target):
            lpm.p.update({"mu": 5.0 + 0.01 * index, "sigma": 1.0})
            conv.convolve(lpm)
        completed = target
        assert tracer.calls == calls_after_prepare

    assert distribution_calls == 100


def test_constant_tracer_uses_minimal_prepared_grid():
    conv = Convolution(ConstantTracer(concentration=1.0, datemin=1900.0), 2010.0)
    grid = conv.prepare()

    assert np.array_equal(grid.edges, np.array([0.0, 110.0]))
    assert np.array_equal(grid.midpoints, np.array([55.0]))
    assert np.array_equal(grid.k_mid, np.array([1.0]))


def test_chronicle_nodes_are_preserved_as_prepared_grid_edges():
    tracer = Tracer(test_paths.tracer_data_dir(), "cfc11")
    conv = Convolution(tracer, 2010.0)
    grid = conv.prepare()
    expected_ages = 2010.0 - np.asarray(tracer.convolution_dates, dtype=float)
    expected_ages = expected_ages[
        (expected_ages >= 0.0) & (expected_ages <= 2010.0 - tracer.datemin)
    ]

    assert np.all(np.isin(expected_ages, grid.edges))


def test_synthetic_tracer_without_nodes_gets_a_safe_initial_grid():
    date = 2010.0
    tmax = 110.0
    tracer = SyntheticTracer(
        datemin=date - tmax,
        concentration_fn=lambda sample_date, age: (
            1.0 + 0.9 * np.sin(4.0 * np.pi * np.asarray(age) / tmax)
        ),
    )
    lpm = lpm_build("uniform", directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update({"tmin": tmax / 8.0 - 0.05, "delta": 0.1})
    conv = Convolution(tracer, date)
    expected = quad(
        lambda age: (
            float(tracer.get_concentration(date - age, age)) * float(lpm.pdf(age))
        ),
        lpm.p["tmin"],
        lpm.p["tmin"] + lpm.p["delta"],
        epsabs=1e-12,
        epsrel=1e-12,
    )[0]

    assert conv.convolve(lpm) == pytest.approx(expected, rel=1e-2)
    assert len(conv.prepared_grid.k_mid) > 1


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("ig", {"mu": 20.0, "sigma": 12.0}),
        ("ig_shifted", {"mu": 20.0, "sigma": 12.0, "shift": 5.0}),
    ],
)
def test_inverse_gaussian_integrates_linear_tracer_with_truncated_moment(
    name,
    parameters,
):
    tracer = SyntheticTracer(
        datemin=1900.0,
        concentration_fn=lambda date, age: 2.0 + 0.01 * np.asarray(age),
    )
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update(parameters)
    conv = Convolution(tracer, 2010.0)
    mass, partial_moment = lpm.cdf_and_partial_first_moment(110.0)
    expected = 2.0 * mass + 0.01 * partial_moment

    assert conv.convolve(lpm) == pytest.approx(expected, rel=2e-13, abs=2e-13)


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("exp", {"mu": 10.0}),
        ("exp_shifted", {"mu": 10.0, "shift": 5.0}),
        ("gamma", {"k": 2.0, "scale": 10.0}),
        ("uniform", {"tmin": 5.0, "delta": 0.5}),
        ("weibull", {"k": 1.7, "lambda": 12.0}),
        ("ig", {"mu": 10.0, "sigma": 2.0}),
        ("ig_shifted", {"mu": 10.0, "sigma": 2.0, "shift": 5.0}),
        ("shapefree_n_oldbin", {}),
    ],
)
def test_all_continuous_lpm_integrate_linear_tracer_from_mass_and_moment(
    name,
    parameters,
):
    tracer = SyntheticTracer(
        datemin=1900.0,
        convolution_initial_bins=1,
        concentration_fn=lambda date, age: 2.0 + 0.01 * np.asarray(age),
    )
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update(parameters)
    mass, partial_moment = lpm.cdf_and_partial_first_moment(110.0)
    expected = 2.0 * mass + 0.01 * partial_moment

    assert Convolution(tracer, 2010.0).convolve(lpm) == pytest.approx(
        expected,
        rel=2e-13,
        abs=2e-13,
    )


def test_mixed_dirac_exponential_integrates_linear_tracer_exactly():
    tracer = SyntheticTracer(
        datemin=1900.0,
        convolution_initial_bins=1,
        concentration_fn=lambda date, age: 2.0 + 0.01 * np.asarray(age),
    )
    lpm = _mixed_lpm(rate=0.3)
    conv = Convolution(tracer, 2010.0)
    mass, partial_moment = lpm.continuous_cdf_and_partial_first_moment(110.0)
    expected = 0.3 * (2.0 + 0.01 * lpm.get_dirac_time()) + 0.7 * (
        2.0 * mass + 0.01 * partial_moment
    )

    assert conv.convolve(lpm) == pytest.approx(expected, rel=2e-13, abs=2e-13)
    assert conv.diagnostics.window_mass == pytest.approx(
        conv.window_mass(lpm),
        rel=2e-14,
        abs=2e-14,
    )


class _CdfOnlyShiftedExponential:
    name = "cdf_only_shifted_exponential"
    convolution_strategy = ConvolutionStrategy.CONTINUOUS
    p = {}

    @staticmethod
    def cdf(ages):
        return expon.cdf(ages, loc=3.7, scale=0.2)


def test_continuous_lpm_without_partial_moment_is_rejected():
    tracer = SyntheticTracer(
        datemin=1900.0,
        convolution_initial_bins=1,
        concentration_fn=lambda date, age: 2.0 + 0.01 * np.asarray(age),
    )
    lpm = _CdfOnlyShiftedExponential()
    with pytest.raises(
        ConvolutionError,
        match="must implement cdf_and_partial_first_moment",
    ):
        Convolution(tracer, 2010.0).convolve(lpm)


def test_chronicle_end_discontinuity_is_a_bin_boundary_not_a_refinement_loop():
    tracer = SyntheticTracer(
        datemin=1900.0,
        datemax=2010.0,
        convolution_dates=np.array([1900.0, 2010.0]),
        concentration_fn=lambda sample_date, age: np.where(
            np.asarray(sample_date) <= 2010.0,
            5.0,
            0.0,
        ),
    )
    lpm = lpm_build("exp", directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p["mu"] = 10.0
    conv = Convolution(tracer, 2012.0)
    expected = 5.0 * (float(lpm.cdf(112.0)) - float(lpm.cdf(2.0)))

    assert conv.convolve(lpm) == pytest.approx(expected, rel=2e-13, abs=2e-13)
    assert conv.diagnostics.n_bins == 2


AUDIT_CASES = [
    ("exp", {"mu": 0.1}, "39Ar"),
    ("exp_shifted", {"mu": 0.1, "shift": 5.0}, "39Ar"),
    ("ig", {"mu": 0.5, "sigma": 0.1}, "39Ar"),
    ("ig", {"mu": 10.0, "sigma": 2.0}, "cfc11"),
    ("ig_shifted", {"mu": 0.5, "sigma": 0.1, "shift": 5.0}, "cfc11"),
    ("ig_shifted", {"mu": 5.0, "sigma": 2.0, "shift": 20.0}, "cfc11"),
    ("gamma", {"k": 10.0, "scale": 0.1}, "cfc11"),
    ("gamma", {"k": 10.0, "scale": 0.1}, "39Ar"),
    ("gamma", {"k": 0.5, "scale": 50.0}, "cfc11"),
    ("uniform", {"tmin": 5.0, "delta": 0.5}, "cfc11"),
    ("uniform", {"tmin": 50.0, "delta": 0.5}, "cfc11"),
    ("uniform", {"tmin": 50.0, "delta": 0.5}, "39Ar"),
    ("uniform", {"tmin": 0.0, "delta": 50.0}, "cfc11"),
    ("weibull", {"k": 10.0, "lambda": 0.1}, "39Ar"),
    ("weibull", {"k": 0.1, "lambda": 100.0}, "39Ar"),
]


def _quantile_quad_reference(tracer, lpm, date):
    """Independent expectation integral in probability rather than PDF space."""
    tmax = date - tracer.datemin
    p_start = float(lpm.cdf(0.0))
    p_end = float(lpm.cdf(tmax))
    if p_end <= p_start:
        return 0.0

    probability_breaks = []
    chronicle_dates = tracer.convolution_dates
    if chronicle_dates is not None:
        ages = date - np.asarray(chronicle_dates, dtype=float)
        ages = ages[(ages > 0.0) & (ages < tmax)]
        probability_breaks = np.asarray(lpm.cdf(ages), dtype=float)
        probability_breaks = np.unique(
            probability_breaks[
                (probability_breaks > p_start) & (probability_breaks < p_end)
            ]
        ).tolist()

    def integrand(probability):
        age = float(lpm.cdf_inv(probability))
        return float(tracer.get_concentration(date - age, age))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", IntegrationWarning)
        return quad(
            integrand,
            p_start,
            p_end,
            points=probability_breaks or None,
            epsabs=1e-9,
            epsrel=1e-9,
            limit=1000,
        )[0]


@pytest.mark.parametrize(("name", "parameters", "tracer_name"), AUDIT_CASES)
def test_audit_failures_match_independent_quantile_quad(name, parameters, tracer_name):
    tracer = Tracer(test_paths.tracer_data_dir(), tracer_name)
    lpm = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.p.update(parameters)
    conv = Convolution(tracer, date=2010.0)

    value = conv.convolve(lpm)
    reference = _quantile_quad_reference(tracer, lpm, 2010.0)

    assert value == pytest.approx(reference, rel=2e-4, abs=1e-8)
    assert conv.diagnostics.window_mass == pytest.approx(
        conv.window_mass(lpm), rel=2e-14, abs=2e-14
    )
    assert conv.diagnostics.window_mass <= 1.0 + 2e-14
