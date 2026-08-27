# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Deterministic edge contracts for parametric and empirical priors."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pyages.calibration.methods.prior import Prior, make_prior_expo, moments_histo


class _TwoParameterModel:
    def __init__(self) -> None:
        self.p = {"mu": 0.0, "width": 0.0}

    def get_p_min(self, name):
        return {"mu": 0.0, "width": 1.0}[name]

    def get_p_max(self, name):
        return {"mu": 10.0, "width": 9.0}[name]

    def get_param_names(self):
        return list(self.p)

    def set_param_from_array(self, values):
        self.p.update(zip(self.p, values, strict=True))


def test_exponential_prior_extension_is_positive_and_normalized() -> None:
    values, density = make_prior_expo(
        [2.0, 3.0],
        [1.0, 0.5],
        xmin=0.0,
        xmax=5.0,
        n_points=2001,
        decay_left=2.0,
        decay_right=3.0,
    )

    assert density[0] > 0.0
    assert density[-1] > 0.0
    assert np.trapezoid(density, values) == pytest.approx(1.0, rel=1e-6)


@pytest.mark.parametrize(
    "density",
    [
        [0.0, 0.0, 0.0],
        [-1.0, -1.0, -1.0],
        [1.0, np.nan, 1.0],
    ],
    ids=["zero", "negative", "nonfinite"],
)
def test_histogram_moments_require_positive_finite_mass(density) -> None:
    histogram = np.column_stack(([0.0, 1.0, 2.0], density))

    with pytest.raises(ValueError, match="positive finite mass"):
        moments_histo(histogram)


def test_parametric_map_initialization_clips_to_model_bounds() -> None:
    model = _TwoParameterModel()
    prior = Prior(typ="parametric")
    prior.MHapriori_dist = {"mu": "normal", "width": "uniform"}
    prior.MHapriori_para = {"mu": [12.0, 2.0], "width": [-4.0, 4.0]}

    prior.param_init(model, strategy="map")

    assert model.p == {"mu": 10.0, "width": 1.0}


def test_parametric_sample_initialization_is_seeded_and_bounded() -> None:
    prior = Prior(typ="parametric")
    prior.MHapriori_dist = {"mu": "normal", "width": "uniform"}
    prior.MHapriori_para = {"mu": [5.0, 2.0], "width": [2.0, 8.0]}
    first = _TwoParameterModel()
    second = _TwoParameterModel()

    prior.param_init(first, strategy="sample", rng=np.random.default_rng(123))
    prior.param_init(second, strategy="sample", rng=np.random.default_rng(123))

    assert first.p == second.p
    assert 0.0 <= first.p["mu"] <= 10.0
    assert 1.0 <= first.p["width"] <= 9.0


def test_empirical_initialization_handles_map_sample_and_zero_mass() -> None:
    model = _TwoParameterModel()
    prior = Prior(typ="empirical")
    prior.MHapriori_para = {
        "mu": np.array([[0.0, 0.0], [4.0, 2.0], [10.0, 0.0]]),
        "width": np.array([[1.0, 0.0], [5.0, 0.0], [9.0, 0.0]]),
    }

    prior.param_init(model, strategy="map")
    assert model.p == {"mu": 4.0, "width": 5.0}

    prior.MHapriori_para["width"][:, 1] = [0.0, 1.0, 0.0]
    prior.param_init(model, strategy="sample", rng=np.random.default_rng(7))
    assert 0.0 <= model.p["mu"] <= 10.0
    assert 1.0 <= model.p["width"] <= 9.0


def test_prior_initialization_rejects_unknown_strategy_and_distribution() -> None:
    model = _TwoParameterModel()
    prior = Prior(typ="parametric")

    with pytest.raises(ValueError, match="strategy"):
        prior.param_init(model, strategy="median")

    prior.MHapriori_dist = {"mu": "triangular", "width": "uniform"}
    prior.MHapriori_para = {"mu": [1.0, 2.0], "width": [1.0, 9.0]}
    with pytest.raises(ValueError, match="Unsupported prior distribution"):
        prior.param_init(model)


def test_parametric_density_and_log_density_are_consistent() -> None:
    model = _TwoParameterModel()
    prior = Prior(typ="parametric")
    prior.MHapriori_dist = {"mu": "normal", "width": "uniform"}
    prior.MHapriori_para = {"mu": [5.0, 2.0], "width": [1.0, 9.0]}

    density = prior.evaluate(model, [6.0, 4.0])

    assert prior.log_evaluate(model, [6.0, 4.0]) == pytest.approx(math.log(density))
    assert prior.log_evaluate(model, [6.0, 10.0]) == -math.inf


@pytest.mark.parametrize(
    ("distribution", "parameters", "message"),
    [
        ("normal", [5.0, 0.0], "std must be positive"),
        ("uniform", [4.0, 4.0], "bounds are invalid"),
        ("lognormal", [1.0, 1.0], "Unsupported prior distribution"),
    ],
)
def test_log_prior_rejects_invalid_parametric_definitions(
    distribution, parameters, message
) -> None:
    model = _TwoParameterModel()
    model.p = {"mu": 0.0}
    prior = Prior(typ="parametric")
    prior.MHapriori_dist = {"mu": distribution}
    prior.MHapriori_para = {"mu": parameters}

    with pytest.raises(ValueError, match=message):
        prior.log_evaluate(model, [4.0])


def test_empirical_prior_has_exact_support_and_rejects_zero_density() -> None:
    model = _TwoParameterModel()
    model.p = {"mu": 0.0}
    prior = Prior(typ="empirical")
    prior.MHapriori_para = {"mu": np.array([[0.0, 0.0], [1.0, 0.5], [2.0, np.nan]])}

    assert prior.evaluate(model, [-1.0]) == 0.0
    assert prior.log_evaluate(model, [-1.0]) == -math.inf
    assert prior.log_evaluate(model, [0.0]) == -math.inf
    assert prior.log_evaluate(model, [2.0]) == -math.inf
    assert prior.log_evaluate(model, [1.0]) == pytest.approx(math.log(0.5))


def test_prior_load_is_a_noop_when_disabled_and_rejects_unknown_type() -> None:
    Prior(option=False, typ="unknown").load(object())

    with pytest.raises(ValueError, match="Unsupported prior type"):
        Prior(option=True, typ="unknown").load(object())


def test_prior_validation_reports_parametric_theory() -> None:
    model = _TwoParameterModel()
    prior = Prior(typ="parametric")
    prior.MHapriori_dist = {"mu": "normal", "width": "uniform"}
    prior.MHapriori_para = {"mu": [5.0, 2.0], "width": [1.0, 9.0]}
    path = pd.DataFrame({"mu": [3.0, 5.0, 7.0], "width": [1.0, 5.0, 9.0]})

    result = prior.validation_MH_prior(path, model)

    assert result["theory"]["mu"] == {"mean": 5.0, "var": 4.0}
    assert result["theory"]["width"]["mean"] == 5.0
    assert result["theory"]["width"]["var"] == pytest.approx(64.0 / 12.0)
