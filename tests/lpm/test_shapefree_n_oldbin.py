# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from __future__ import annotations

from textwrap import dedent

import numpy as np
import pytest

from pyages.convolution import Convolution
from pyages.lpm import build_lpm
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.tracer.simple_tracers import SyntheticTracer
from tests.utils import paths as test_paths


def _make_lpm():
    lpm = build_lpm("shapefree_n_oldbin", directory_lpm=str(test_paths.lpm_data_dir()))
    lpm.set_param_from_array([0.0, 0.0, 0.0])
    return lpm


def _make_support_open_lpm(tmp_path):
    data_dir = tmp_path / "data_lpm"
    model_dir = data_dir / "shapefree_n_oldbin"
    model_dir.mkdir(parents=True)
    (model_dir / "params.yaml").write_text(
        dedent(
            """
            model: shapefree_n_oldbin
            version: 1

            shapefree:
              mode: support_open
              edges: [0.0, 10.0, 30.0]
              labels: ["0-10", "10-30", "old"]
              parameterization: stick_breaking
              support_end_max: 100.0

            parameters:
              - name: z1
                label: latent_fraction_1
                unit: "-"
                calibration_range: [-8.0, 8.0]
                init: 0.0
                step: 0.5
                prior:
                  type: uniform
                  min: -8.0
                  max: 8.0
                  unit: "-"

              - name: z2
                label: latent_fraction_2
                unit: "-"
                calibration_range: [-8.0, 8.0]
                init: 0.0
                step: 0.5
                prior:
                  type: uniform
                  min: -8.0
                  max: 8.0
                  unit: "-"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    lpm = build_lpm("shapefree_n_oldbin", directory_lpm=str(data_dir))
    lpm.set_param_from_array([0.0, 0.0])
    return lpm


def test_shapefree_n_oldbin_fraction_closure():
    lpm = _make_lpm()

    fractions = lpm.fractions()

    assert lpm.bin_edges().tolist() == [0.0, 20.0, 40.0, 60.0, 200.0]
    assert fractions.tolist() == [0.5, 0.25, 0.125, 0.125]
    assert float(fractions.sum()) == 1.0
    assert lpm.convolution_strategy is ConvolutionStrategy.PIECEWISE_UNIFORM


def test_shapefree_n_oldbin_piecewise_pdf_cdf():
    lpm = _make_lpm()

    pdf = np.asarray(lpm.pdf(np.array([10.0, 30.0, 50.0, 130.0], dtype=float)))
    cdf = np.asarray(lpm.cdf(np.array([20.0, 40.0, 60.0, 200.0], dtype=float)))

    assert np.allclose(pdf, np.array([0.025, 0.0125, 0.00625, 0.125 / 140.0]))
    assert np.allclose(cdf, np.array([0.5, 0.75, 0.875, 1.0]))
    assert float(lpm.cdf_inv(0.5)) == 20.0
    assert float(lpm.cdf_inv(0.75)) == 40.0
    assert float(lpm.cdf_inv(0.875)) == 60.0


def test_shapefree_n_oldbin_support_open_dynamic_tail(tmp_path):
    lpm = _make_support_open_lpm(tmp_path)

    assert lpm.bin_edges().tolist() == [0.0, 10.0, 30.0, 100.0]
    assert lpm.fractions().tolist() == [0.5, 0.25, 0.25]

    pdf_default = np.asarray(lpm.pdf(np.array([5.0, 20.0, 65.0, 105.0], dtype=float)))

    assert np.allclose(pdf_default, np.array([0.05, 0.0125, 0.25 / 70.0, 0.0]))
    assert float(lpm.cdf_inv(0.875)) == 65.0


def test_shapefree_n_oldbin_support_open_respects_lpm_max(tmp_path):
    lpm = _make_support_open_lpm(tmp_path)

    pdf_capped = np.asarray(lpm.pdf(np.array([35.0, 95.0, 105.0], dtype=float)))

    assert np.allclose(pdf_capped, np.array([0.25 / 70.0, 0.25 / 70.0, 0.0]))
    assert lpm.bin_edges().tolist() == [0.0, 10.0, 30.0, 100.0]


def test_shapefree_n_oldbin_support_open_convolution_truncates_on_traceur_support(
    tmp_path,
):
    lpm = _make_support_open_lpm(tmp_path)
    tracer = SyntheticTracer(
        name="linear_time",
        datemin=1970.0,
        datemax=2100.0,
        concentration_fn=lambda date, time: np.asarray(time, dtype=float),
    )

    value = Convolution(tracer, date=2010.0).convolve(lpm)

    assert value == pytest.approx(8.75, abs=0.05)
