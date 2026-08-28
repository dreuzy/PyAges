# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Boundary and plotting contracts for temporal concentration predictions."""

from __future__ import annotations

import matplotlib
import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

from pyages.concentrations import Concentrations
from pyages.concentrations.plotting import (
    plot_concentration_chronicles_summary,
)
from pyages.concentrations.temporal import summarize_temporal_predictions


def _prediction_frame(dates=(2000.0, 2001.0), values=(1.0, 2.0)) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "concentration": values})


class _SequentialTemporalTracers:
    def __init__(self, realizations):
        self.realizations = list(realizations)

    def convolve_date_range(self, realization, start_year, end_year):
        del start_year, end_year
        return self.realizations[realization]


def test_temporal_summary_requires_at_least_one_lpm() -> None:
    with pytest.raises(ValueError, match="At least one calibrated LPM"):
        summarize_temporal_predictions(object(), [], 1960.0, 2020.0)


def test_temporal_summary_rejects_an_empty_tracer_set() -> None:
    tracers = _SequentialTemporalTracers([{}])

    with pytest.raises(ValueError, match="no tracer series"):
        summarize_temporal_predictions(tracers, [0], 1960.0, 2020.0)


def test_temporal_summary_reports_inconsistent_tracer_sets() -> None:
    tracers = _SequentialTemporalTracers(
        [
            {"cfc11": _prediction_frame()},
            {"cfc12": _prediction_frame()},
        ]
    )

    with pytest.raises(ValueError) as error:
        summarize_temporal_predictions(tracers, [0, 1], 1960.0, 2020.0)

    message = str(error.value)
    assert "realization 1" in message
    assert "missing=['cfc11']" in message
    assert "extra=['cfc12']" in message


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (pd.DataFrame({"concentration": [1.0]}), "missing columns: date"),
        (pd.DataFrame({"date": [2000.0]}), "missing columns: concentration"),
        (_prediction_frame(dates=(), values=()), "must not be empty"),
        (_prediction_frame(dates=(2000.0, np.nan)), "must be finite"),
        (_prediction_frame(values=(1.0, np.inf)), "must be finite"),
        (_prediction_frame(dates=(2000.0, 2000.0)), "duplicate dates"),
    ],
    ids=[
        "missing-date",
        "missing-concentration",
        "empty",
        "nonfinite-date",
        "nonfinite-concentration",
        "duplicate-date",
    ],
)
def test_temporal_summary_rejects_invalid_prediction_frames(
    frame: pd.DataFrame, message: str
) -> None:
    tracers = _SequentialTemporalTracers([{"cfc11": frame}])

    with pytest.raises(ValueError, match=message):
        summarize_temporal_predictions(tracers, [0], 1960.0, 2020.0)


def test_zero_truncated_sampling_preserves_deterministic_rows() -> None:
    concentrations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["3H", "3H", "3H"],
                "concentration": [0.25, 0.10, 4.0],
                "error": [0.0, 1.0, 0.0],
                "unit": ["TU", "TU", "TU"],
                "date": [2000.0, 2001.0, 2002.0],
            }
        )
    )

    sampled = concentrations.sample_with_errors(np.random.default_rng(42))

    assert sampled.frame.loc[[0, 2], "concentration"].tolist() == [0.25, 4.0]
    assert sampled.frame.loc[1, "concentration"] > 0.0


def test_zero_truncated_sampling_matches_the_analytic_mean() -> None:
    sample_count = 20_000
    location = 0.1
    scale = 1.0
    concentrations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["3H"] * sample_count,
                "concentration": [location] * sample_count,
                "error": [scale] * sample_count,
                "unit": ["TU"] * sample_count,
                "date": np.arange(sample_count, dtype=float),
            }
        )
    )

    sampled = concentrations.sample_with_errors(np.random.default_rng(2026))
    values = sampled.frame["concentration"].to_numpy(dtype=float)
    standardized_lower_bound = -location / scale
    expected_mean = location + scale * norm.pdf(standardized_lower_bound) / (
        1.0 - norm.cdf(standardized_lower_bound)
    )

    assert np.all(values > 0.0)
    assert float(values.mean()) == pytest.approx(expected_mean, abs=0.02)


def test_chronicle_summary_plots_shared_quantiles_and_removes_extra_axes() -> None:
    observations = Concentrations.from_dataframe(
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
    tracers = _SequentialTemporalTracers(
        [
            {"cfc11": _prediction_frame(values=(1.0, 10.0))},
            {"cfc11": _prediction_frame(values=(3.0, 30.0))},
        ]
    )
    figure, axes = plt.subplots(1, 2)
    summaries = summarize_temporal_predictions(
        tracers,
        [0, 1],
        start_year=1960.0,
        end_year=2001.0,
    )

    try:
        plot_concentration_chronicles_summary(
            axes,
            observations,
            summaries,
        )

        median_line = next(
            line for line in axes[0].lines if line.get_label() == "Median model"
        )
        assert median_line.get_xdata().tolist() == [2000.0, 2001.0]
        assert median_line.get_ydata().tolist() == [2.0, 20.0]
        assert set(axes[0].get_legend_handles_labels()[1]) >= {
            "90% interval",
            "50% interval",
            "Median model",
            "Observations",
        }
        assert axes[1] not in figure.axes
    finally:
        plt.close(figure)
