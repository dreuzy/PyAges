# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Integration contracts for temporal posterior summary figures."""

from __future__ import annotations

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

from pyages.concentrations import Concentrations
from pyages.workflows.plots import temporal as temporal_plots


class _TemporalTracers:
    def validate_observation_units(self, observations):
        assert observations.units_by_tracer() == {"cfc11": "pptv"}

    def convolve_date_range(self, realization, start_year, end_year):
        del start_year, end_year
        return {
            "cfc11": pd.DataFrame(
                {
                    "date": [2000.0, 2001.0],
                    "concentration": realization,
                }
            )
        }


class _PosteriorResults:
    def __init__(self, realizations):
        self.realizations = realizations
        self.calls = []

    def select(self, *, count, resolution):
        self.calls.append((count, resolution))
        return self.realizations, None, None


def _observations() -> Concentrations:
    return Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc11"],
                "concentration": [1.5, 2.5],
                "error": [0.1, 0.2],
                "unit": ["pptv", "pptv"],
                "date": [2000.0, 2001.0],
            }
        )
    )


def test_temporal_fit_summary_plots_selected_posterior_quantiles(
    tmp_path, monkeypatch
) -> None:
    tracers = _TemporalTracers()
    monkeypatch.setattr(
        temporal_plots.convolution_tracers,
        "ConvolutionTracers",
        lambda **_kwargs: tracers,
    )
    results = _PosteriorResults([[1.0, 10.0], [3.0, 30.0]])
    output = tmp_path / "temporal-summary.png"

    figure = temporal_plots.plot_temporal_fit_summary(
        _observations(),
        results,
        lpm_number=2,
        filename=output,
        title="Audited temporal fit",
    )
    try:
        axis = figure.axes[0]
        median_line = axis.lines[0]
        assert results.calls == [(2, 1000)]
        assert median_line.get_xdata().tolist() == [2000.0, 2001.0]
        assert median_line.get_ydata().tolist() == [2.0, 20.0]
        assert [text.get_text() for text in figure.legends[0].get_texts()] == [
            "Observations",
            "Median model",
            "50% interval",
            "90% interval",
        ]
        assert output.is_file()
    finally:
        plt.close(figure)


def test_temporal_fit_summary_rejects_an_empty_posterior(monkeypatch) -> None:
    monkeypatch.setattr(
        temporal_plots.convolution_tracers,
        "ConvolutionTracers",
        lambda **_kwargs: _TemporalTracers(),
    )
    results = _PosteriorResults([])

    with pytest.raises(ValueError, match="No calibrated LPMs"):
        temporal_plots.plot_temporal_fit_summary(_observations(), results, lpm_number=1)
