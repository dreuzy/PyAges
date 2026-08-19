"""Analytical partial-first-moment contracts for continuous LPMs."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.lpm_build import lpm_build
from tests.utils import paths as test_paths

MODEL_CASES = [
    ("exp", {"mu": 10.0}, 12.0),
    ("exp_shifted", {"mu": 10.0, "shift": 5.0}, 17.0),
    ("gamma", {"k": 2.5, "scale": 4.0}, 12.0),
    ("uniform", {"tmin": 5.0, "delta": 10.0}, 12.0),
    ("weibull", {"k": 1.7, "lambda": 12.0}, 15.0),
    ("ig", {"mu": 10.0, "sigma": 2.0}, 12.0),
    ("ig_shifted", {"mu": 10.0, "sigma": 2.0, "shift": 5.0}, 17.0),
    ("shapefree_n_oldbin", {}, 50.0),
]


def _model(name, parameters):
    model = lpm_build(name, directory_lpm=str(test_paths.lpm_data_dir()))
    model.p.update(parameters)
    return model


def _breakpoints(model, upper):
    points = []
    if "shift" in model.p:
        points.append(float(model.p["shift"]))
    if model.name == "uniform":
        points.extend(
            [
                float(model.p["tmin"]),
                float(model.p["tmin"] + model.p["delta"]),
            ]
        )
    if model.name == "shapefree_n_oldbin":
        points.extend(model.bin_edges().tolist())
    return sorted(set(point for point in points if 0.0 < point < upper))


@pytest.mark.parametrize(("name", "parameters", "upper"), MODEL_CASES)
def test_partial_first_moment_matches_independent_pdf_quad(name, parameters, upper):
    model = _model(name, parameters)

    cdf, partial_moment = model.cdf_and_partial_first_moment(upper)
    reference = quad(
        lambda age: age * float(model.pdf(age)),
        0.0,
        upper,
        points=_breakpoints(model, upper) or None,
        epsabs=1.0e-11,
        epsrel=1.0e-11,
        limit=1000,
    )[0]

    assert cdf == pytest.approx(model.cdf(upper), rel=2e-13, abs=2e-14)
    assert partial_moment == pytest.approx(reference, rel=2e-11, abs=2e-12)


@pytest.mark.parametrize(("name", "parameters", "_upper"), MODEL_CASES)
def test_partial_first_moment_vectorization_and_total_mean(name, parameters, _upper):
    model = _model(name, parameters)
    ages = np.array([-1.0, 0.0, 0.1, 1.0, 10.0, 100.0, np.inf])

    cdf, partial_moment = model.cdf_and_partial_first_moment(ages)

    assert cdf.shape == ages.shape
    assert partial_moment.shape == ages.shape
    assert cdf == pytest.approx(model.cdf(ages), rel=2e-13, abs=2e-14)
    assert np.all(np.diff(cdf) >= -2e-15)
    assert np.all(np.diff(partial_moment) >= -2e-13)
    assert cdf[-1] == pytest.approx(1.0, rel=2e-13, abs=2e-14)
    assert partial_moment[-1] == pytest.approx(model.mean(), rel=2e-11, abs=2e-12)


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("exp", {"mu": 0.1}),
        ("exp_shifted", {"mu": 0.1, "shift": 3.7}),
        ("gamma", {"k": 0.1, "scale": 80.0}),
        ("gamma", {"k": 10.0, "scale": 0.1}),
        ("uniform", {"tmin": 50.0, "delta": 0.5}),
        ("weibull", {"k": 0.1, "lambda": 100.0}),
        ("weibull", {"k": 10.0, "lambda": 0.1}),
    ],
)
def test_partial_first_moment_is_finite_at_parameter_bounds(name, parameters):
    model = _model(name, parameters)
    ages = np.array([0.0, 1.0e-8, 0.1, 1.0, 10.0, 100.0, 10_000.0])

    cdf, partial_moment = model.cdf_and_partial_first_moment(ages)

    assert np.all(np.isfinite(cdf))
    assert np.all(np.isfinite(partial_moment))
    assert np.all((cdf >= 0.0) & (cdf <= 1.0))
    assert np.all(partial_moment >= 0.0)
    assert np.all(np.diff(partial_moment) >= -2e-13)


@pytest.mark.parametrize(
    "name",
    ["exp", "exp_shifted"],
)
def test_exponential_family_uses_common_continuous_strategy(name):
    model = _model(name, {})

    assert model.convolution_strategy is ConvolutionStrategy.CONTINUOUS
