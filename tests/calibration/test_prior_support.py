# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Support behavior for generic calibration priors."""

import math
from pathlib import Path

import pandas as pd
import pytest

from pyages.calibration.methods.prior import Prior
from pyages.data_io.lpm_distribution import write_frame
from pyages.lpm import build_lpm


class _OneParameterModel:
    p = {"mu": 0.0}


class _TwoParameterModel:
    name = "custom"
    p = {"mu": 0.0, "sigma": 1.0}

    def __init__(self, data_directory: Path) -> None:
        self.lpm_data_directory = data_directory


def test_uniform_prior_has_exact_zero_support():
    prior = Prior(option=True, typ="parametric")
    prior.MHapriori_dist = {"mu": "uniform"}
    prior.MHapriori_para = {"mu": [1.0, 2.0]}
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
    bounds: [0.0, 10.0]
    init: 1.0
    prior:
      type: uniform
      min: 0.0
      max: 10.0
  - name: sigma
    bounds: [0.1, 10.0]
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

    assert list(prior.MHapriori_para) == ["mu"]
    assert prior.MHapriori_para["mu"].shape == (101, 2)
