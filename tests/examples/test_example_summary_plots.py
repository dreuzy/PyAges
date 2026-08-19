# -*- coding: utf-8 -*-
"""
Smoke tests for reusable example plotting helpers.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import pyage.concentrations.concentrations as co
from pyage.workflows.summary_plots import (
    plot_parameter_distribution_comparison,
    plot_temporal_fit_comparison,
)


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
            "unit": ["TU", "TU", "pmc", "pmc"],
        }
    )
    cdata = co.Concentrations(dataframe_load=True, dataframe_concentration=observed)
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
        craw=cdata,
        posterior_frames={
            "Transient posterior": transient,
            "Single-date posterior": single_date,
        },
        lpm_name="exp_shifted",
        lpm_directory="data_core/data_lpm",
        selection_modes={
            "Transient posterior": "span",
            "Single-date posterior": "single_date",
        },
        lpm_number=6,
        filename=out_path,
        title="Temporal fit comparison",
    )

    assert out_path.exists()
    assert len(fig.axes) >= 2
    plt.close(fig)
