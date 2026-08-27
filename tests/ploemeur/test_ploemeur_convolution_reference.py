# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Independent convolution references for Ploemeur posterior regimes."""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from scipy.integrate import IntegrationWarning, quad

from pyages.config.paths import DIRECTORY_TRACER_DATA
from pyages.convolution.convolution import Convolution
from pyages.lpm import build_lpm
from pyages.tracer.tracer_root import Tracer

LPM_DIRECTORY = "sites/ploemeur/params_lpm"
POSTERIOR_REGIMES = [
    # Independent 2005-2006 window: broad IG tail and a measurable truncation.
    (
        2005.435616438356,
        {"mu": 4.090446369, "sigma": 11.131176268, "shift": 0.446552775},
    ),
    # Full 2005-2024 span.
    (
        2005.435616438356,
        {"mu": 1.536183584, "sigma": 2.366156523, "shift": 1.979377193},
    ),
    # Prior-conditioned 2016-2017 window.
    (
        2016.093150684932,
        {"mu": 1.816762645, "sigma": 2.100338886, "shift": 1.221586623},
    ),
]


def _probability_space_reference(tracer: Tracer, lpm, date: float) -> float:
    """Integrate K(F^-1(p)) independently in probability space."""
    maximum_age = date - tracer.datemin
    probability_start = float(lpm.cdf(0.0))
    probability_end = float(lpm.cdf(maximum_age))
    chronicle_dates = tracer.convolution_dates
    probability_breaks: list[float] = []
    if chronicle_dates is not None:
        ages = date - np.asarray(chronicle_dates, dtype=float)
        ages = ages[(ages > 0.0) & (ages < maximum_age)]
        values = np.asarray(lpm.cdf(ages), dtype=float)
        probability_breaks = np.unique(
            values[(values > probability_start) & (values < probability_end)]
        ).tolist()

    def integrand(probability: float) -> float:
        age = float(lpm.cdf_inv(probability))
        return float(tracer.get_concentration(date - age, age))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", IntegrationWarning)
        return quad(
            integrand,
            probability_start,
            probability_end,
            points=probability_breaks or None,
            epsabs=1e-9,
            epsrel=1e-9,
            limit=1000,
        )[0]


@pytest.mark.parametrize("tracer_name", ["cfc11", "cfc12"])
@pytest.mark.parametrize(("date", "parameters"), POSTERIOR_REGIMES)
def test_ploemeur_shifted_ig_matches_independent_reference(
    tracer_name: str,
    date: float,
    parameters: dict[str, float],
) -> None:
    tracer = Tracer(DIRECTORY_TRACER_DATA, tracer_name)
    lpm = build_lpm("ig_shifted", directory_lpm=LPM_DIRECTORY)
    lpm.p.update(parameters)
    convolution = Convolution(tracer, date)

    actual = convolution.convolve(lpm)
    expected = _probability_space_reference(tracer, lpm, date)

    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-8)
    assert convolution.diagnostics is not None
    assert 0.0 < convolution.diagnostics.window_mass <= 1.0 + 2e-14
