"""Support behavior for generic calibration priors."""

import math

from pyage.calibration.methods.prior import Prior


class _OneParameterModel:
    p = {"mu": 0.0}


def test_uniform_prior_has_exact_zero_support():
    prior = Prior(option=True, typ="parametric")
    prior.MHapriori_dist = {"mu": "uniform"}
    prior.MHapriori_para = {"mu": [1.0, 2.0]}
    model = _OneParameterModel()

    assert prior.evaluate(model, [0.5]) == 0.0
    assert prior.log_evaluate(model, [0.5]) == -math.inf
