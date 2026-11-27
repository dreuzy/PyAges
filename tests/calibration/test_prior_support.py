# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Support behavior for generic calibration priors."""

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from pyages.calibration.methods.mh._prior_marginals import UniformMarginal
from pyages.calibration.methods.mh._prior_support import (
    open_unit_probability,
    validated_bounds,
)
from pyages.calibration.methods.mh.prior import Prior
from pyages.data_io.lpm_distribution import write_frame
from pyages.lpm import build_lpm


class _OneParameterModel:
    p = {"mu": 0.0}


class _TwoParameterModel:
    name = "custom"
    p = {"mu": 0.0, "sigma": 1.0}

    def __init__(self, data_directory: Path) -> None:
        self.lpm_data_directory = data_directory


@pytest.mark.parametrize(
    "probability", [True, False, "invalid", None, math.nan, math.inf, -0.1, 1.1]
)
def test_open_unit_probability_rejects_invalid_values(probability) -> None:
    with pytest.raises(ValueError, match="finite and in"):
        open_unit_probability(probability)


def test_open_unit_probability_moves_endpoints_inside_support() -> None:
    lower = open_unit_probability(0.0)
    upper = open_unit_probability(1.0)

    assert 0.0 < lower < upper < 1.0
    assert open_unit_probability(0.25) == 0.25


@pytest.mark.parametrize(
    ("minimum", "maximum", "message"),
    [
        (None, 1.0, "finite numbers"),
        (0.0, "invalid", "finite numbers"),
        (math.nan, 1.0, "finite numbers"),
        (0.0, math.inf, "finite numbers"),
        (1.0, 1.0, "strictly increasing"),
        (2.0, 1.0, "strictly increasing"),
    ],
)
def test_validated_bounds_rejects_invalid_intervals(minimum, maximum, message) -> None:
    with pytest.raises(ValueError, match=message):
        validated_bounds(minimum, maximum)


def test_validated_bounds_returns_finite_float_interval() -> None:
    assert validated_bounds("1.5", 3) == (1.5, 3.0)


def test_uniform_prior_has_exact_zero_support():
    prior = Prior(option=True, typ="parametric")
    prior._marginals = {"mu": UniformMarginal("mu", 1.0, 2.0)}  # noqa: SLF001
    model = _OneParameterModel()

    assert prior.evaluate(model, [0.5]) == 0.0
    assert prior.log_evaluate(model, [0.5]) == -math.inf


def test_loading_parametric_priors_requires_every_model_parameter(tmp_path) -> None:
    model_dir = tmp_path / "custom"
    model_dir.mkdir()
    (model_dir / "params.yaml").write_text(
        """model: custom
version: 1
parameters:
  - name: mu
    calibration_range: [0.0, 10.0]
    init: 1.0
    prior:
      type: uniform
      min: 0.0
      max: 10.0
  - name: sigma
    calibration_range: [0.1, 10.0]
    init: 1.0
""",
        encoding="utf-8",
    )
    prior = Prior(option=True, typ="parametric")

    with pytest.raises(ValueError, match=r"missing=\['sigma'\]"):
        prior.load(_TwoParameterModel(tmp_path))


def test_loading_empirical_priors_uses_the_histogram_file_family(tmp_path) -> None:
    model = build_lpm("exp")
    prefix = tmp_path / "posterior"
    write_frame(
        pd.DataFrame({"val": [1.0, 2.0, 3.0], "hist": [0.1, 0.8, 0.1]}),
        tmp_path / "posterior_mu.txt",
        index=False,
    )
    prior = Prior(option=True, typ="empirical", prior_file=str(prefix))

    prior.load(model)

    metadata = prior.resolved_metadata(model)
    assert metadata["prior_distribution_mu"] == "empirical"
    assert metadata["prior_grid_points_mu"] == 101
    assert json.loads(metadata["prior_effective_support_mu"]) == [0.1, 100.0]
