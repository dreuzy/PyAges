# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Smoke tests for reusable example plotting helpers.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

import pyages.reporting.plots.model_space as model_space_module
from pyages.concentrations import Concentrations
from pyages.reporting.plots import (
    plot_objective_solution_map,
    plot_objective_summary,
    plot_observations_overview,
    plot_parameter_distribution_comparison,
    plot_parameter_summary,
    plot_single_date_model_space,
    plot_temporal_fit_comparison,
)


def test_core_summary_plots_smoke(tmp_path: Path) -> None:
    observed = pd.DataFrame(
        {
            "element": ["cfc11", "cfc12"],
            "concentration": [230.0, 470.0],
            "error": [10.0, 15.0],
            "unit": ["pptv", "pptv"],
            "date": [2010.0, 2010.0],
        }
    )
    concentrations = Concentrations.from_dataframe(observed)
    concentration_names = concentrations.observation_keys()
    posterior = pd.DataFrame(
        {
            "mu": [8.0, 10.0, 12.0],
            "shift": [1.0, 2.0, 3.0],
            "obj_function": [1.5, 0.8, 1.1],
            concentration_names[0]: [220.0, 230.0, 240.0],
            concentration_names[1]: [455.0, 470.0, 485.0],
        }
    )
    reachable = pd.DataFrame(
        {
            "cfc11@2010.0": [210.0, 230.0, 250.0],
            "cfc12@2010.0": [440.0, 470.0, 500.0],
        }
    )
    objective = pd.DataFrame(
        {
            "mu": [8.0, 8.0, 12.0, 12.0],
            "shift": [1.0, 3.0, 1.0, 3.0],
            "half_log_chi_square": [1.4, 1.1, 1.2, 0.7],
        }
    )
    figures = [
        plot_observations_overview(
            concentrations,
            filename=tmp_path / "observations.png",
        ),
        plot_single_date_model_space(
            concentrations,
            reachable,
            {"posterior": posterior},
            reference_concentrations=concentrations,
            filename=tmp_path / "model_space.png",
        ),
        plot_parameter_summary(
            {"posterior": posterior},
            ["mu", "shift"],
            filename=tmp_path / "parameters.png",
        ),
        plot_objective_summary(
            objective,
            {"posterior": posterior},
            ["mu", "shift"],
            filename=tmp_path / "objective.png",
        ),
        plot_objective_solution_map(
            objective,
            posterior,
            ["mu", "shift"],
            filename=tmp_path / "objective_solutions.png",
        ),
    ]

    assert len(list(tmp_path.glob("*.png"))) == len(figures)
    for figure in figures:
        plt.close(figure)


def test_model_space_pairs_duplicate_references_by_indexed_observation_key() -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc11"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.1],
                "unit": ["pptv", "pptv"],
                "date": [2010.0, 2010.0],
            }
        )
    )
    references = Concentrations.from_dataframe(
        observations.frame.assign(concentration=[10.0, 20.0])
    )
    reachable = pd.DataFrame({"cfc11@2010.0": [5.0]})

    figure = plot_single_date_model_space(
        observations,
        reachable,
        {},
        reference_concentrations=references,
    )
    try:
        reference_artist = next(
            artist
            for artist in figure.axes[0].collections
            if artist.get_label() == "Reference model"
        )
        np.testing.assert_allclose(
            np.asarray(reference_artist.get_offsets()),
            [[10.0, 20.0]],
        )
    finally:
        plt.close(figure)


def test_model_space_explicit_reference_keys_are_independent_of_row_order() -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc11"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.1],
                "unit": ["pptv", "pptv"],
                "date": [2010.0, 2010.0],
            }
        )
    )
    first_key, second_key = observations.observation_keys()
    references = pd.DataFrame(
        {
            "observation_key": [second_key, first_key],
            "concentration": [20.0, 10.0],
        }
    )

    figure = plot_single_date_model_space(
        observations,
        pd.DataFrame({"cfc11@2010.0": [5.0]}),
        {},
        reference_concentrations=references,
    )
    try:
        reference_artist = next(
            artist
            for artist in figure.axes[0].collections
            if artist.get_label() == "Reference model"
        )
        np.testing.assert_allclose(
            np.asarray(reference_artist.get_offsets()),
            [[10.0, 20.0]],
        )
    finally:
        plt.close(figure)


def test_model_space_rejects_duplicate_explicit_reference_keys() -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc12"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.1],
                "unit": ["pptv", "pptv"],
                "date": [2010.0, 2010.0],
            }
        )
    )
    duplicate_key = observations.observation_keys()[0]
    references = pd.DataFrame(
        {
            "observation_key": [duplicate_key, duplicate_key],
            "concentration": [10.0, 20.0],
        }
    )

    with pytest.raises(ValueError, match="observation_key values must be unique"):
        plot_single_date_model_space(
            observations,
            pd.DataFrame({"cfc11@2010.0": [1.0], "cfc12@2010.0": [2.0]}),
            {},
            reference_concentrations=references,
        )


def test_model_space_rejects_position_based_reference_matching() -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc12"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.1],
                "unit": ["pptv", "pptv"],
                "date": [2010.0, 2010.0],
            }
        )
    )
    references = observations.frame.assign(concentration=[10.0, 20.0])

    with pytest.raises(ValueError, match="observation_key"):
        plot_single_date_model_space(
            observations,
            pd.DataFrame({"cfc11@2010.0": [1.0], "cfc12@2010.0": [2.0]}),
            {},
            reference_concentrations=references,
        )


def test_model_space_prepares_each_posterior_once(monkeypatch) -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11", "cfc12", "sf6", "3H"],
                "concentration": [1.0, 2.0, 3.0, 4.0],
                "error": [0.1, 0.1, 0.1, 0.1],
                "unit": ["pptv", "pptv", "pptv", "TU"],
                "date": [2010.0] * 4,
            }
        )
    )
    reachable = pd.DataFrame(
        {
            "cfc11@2010.0": [1.0],
            "cfc12@2010.0": [2.0],
            "sf6@2010.0": [3.0],
            "3H@2010.0": [4.0],
        }
    )
    posterior = pd.DataFrame(
        {
            **{
                key: [value]
                for key, value in zip(
                    observations.observation_keys(),
                    [1.0, 2.0, 3.0, 4.0],
                    strict=True,
                )
            },
            "obj_function": [0.0],
        }
    )
    real_ensure_frame = model_space_module._ensure_frame
    real_best_row = model_space_module._best_row
    ensure_calls = []
    best_calls = []

    def counted_ensure_frame(result):
        ensure_calls.append(result)
        return real_ensure_frame(result)

    def counted_best_row(frame):
        best_calls.append(frame)
        return real_best_row(frame)

    monkeypatch.setattr(model_space_module, "_ensure_frame", counted_ensure_frame)
    monkeypatch.setattr(model_space_module, "_best_row", counted_best_row)

    figure = plot_single_date_model_space(
        observations,
        reachable,
        {"posterior": posterior},
    )
    try:
        assert ensure_calls == [posterior]
        assert len(best_calls) == 1
    finally:
        plt.close(figure)


def test_plot_parameter_distribution_comparison_smoke(tmp_path: Path) -> None:
    transient = pd.DataFrame(
        {
            "mu": [12.0, 13.5, 14.0, 15.0, 16.0, 16.5],
            "shift": [2.0, 2.4, 2.7, 3.0, 3.2, 3.3],
        }
    )
    single_date = pd.DataFrame(
        {
            "mu": [10.0, 11.0, 12.0, 18.0, 19.0, 20.0],
            "shift": [1.0, 1.4, 1.8, 4.0, 4.2, 4.5],
        }
    )
    out_path = tmp_path / "parameter_distribution_comparison.png"

    fig = plot_parameter_distribution_comparison(
        distributions={
            "Transient posterior": transient,
            "Single-date posterior": single_date,
        },
        param_names=["mu", "shift"],
        filename=out_path,
        title="Transient vs single-date parameter distributions",
    )

    assert out_path.exists()
    assert len(fig.axes) >= 2
    plt.close(fig)


def test_plot_temporal_fit_comparison_smoke(tmp_path: Path) -> None:
    observed = pd.DataFrame(
        {
            "element": ["3H", "3H", "kr85", "kr85"],
            "date": [2010.0, 2012.0, 2010.0, 2012.0],
            "concentration": [4.2, 3.7, 12.1, 10.8],
            "error": [0.2, 0.2, 0.4, 0.4],
            "unit": ["TU", "TU", "pptv", "pptv"],
        }
    )
    observations = Concentrations.from_dataframe(observed)
    transient = pd.DataFrame(
        {
            "mu": [12.0, 13.5, 14.0, 15.0, 16.0, 16.5],
            "shift": [2.0, 2.4, 2.7, 3.0, 3.2, 3.3],
            "obj_function": [1.1, 1.0, 0.9, 0.8, 0.85, 0.95],
        }
    )
    single_date = pd.DataFrame(
        {
            "mu": [10.0, 11.0, 12.0, 18.0, 19.0, 20.0],
            "shift": [1.0, 1.4, 1.8, 4.0, 4.2, 4.5],
            "obj_function": [1.4, 1.2, 1.1, 1.3, 1.35, 1.5],
        }
    )
    out_path = tmp_path / "temporal_fit_comparison.png"

    fig = plot_temporal_fit_comparison(
        observations=observations,
        posterior_frames={
            "Transient posterior": transient,
            "Single-date posterior": single_date,
        },
        lpm_name="exp_shifted",
        lpm_directory="data_core/data_lpm",
        posterior_draw_count=6,
        filename=out_path,
        title="Temporal fit comparison",
    )

    assert out_path.exists()
    assert len(fig.axes) >= 2
    plt.close(fig)
