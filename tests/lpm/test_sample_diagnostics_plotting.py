# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Data-routing tests for LPM posterior diagnostic plots."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

from pyages.lpm import build_lpm
from pyages.lpm.plotting import sample_diagnostics
from pyages.lpm.samples.table import LpmSampleTable


def _sample_table(offset: float = 0.0) -> LpmSampleTable:
    model = build_lpm("ig")
    names = model.get_param_names()
    table = LpmSampleTable(model, c_names=["cfc11", "cfc12"])
    for index in range(4):
        params = {
            name: model.get_calibration_range(name)[0]
            + (0.25 + 0.1 * index) * model.get_calibration_range_width(name)
            + offset
            for name in names
        }
        table.append_sample(
            params,
            obj_function=float(index + 1),
            concentrations=[float(index), float(index + 2)],
            param_in_bounds=True,
        )
    return table


def test_parameter_diagnostics_route_all_one_and_two_dimensional_views(
    tmp_path, monkeypatch, capsys
) -> None:
    distribution = _sample_table()
    comparison = _sample_table(offset=0.01)
    reference = build_lpm("ig")
    closed = []
    pair_plot = Mock()
    monkeypatch.setattr(
        sample_diagnostics.plotting,
        "finalize_figure",
        lambda _figure, filename=None: (closed.append(filename), plt.close()),
    )
    monkeypatch.setattr(
        sample_diagnostics.plotting,
        "plot_histogram_scatter",
        pair_plot,
    )

    sample_diagnostics.plot_parameter_diagnostics(
        distribution,
        self_method="MH",
        lpm_reference=reference,
        lpm_2nd=comparison,
        lpm_2nd_method="comparison",
        directory=tmp_path,
        display_text=True,
    )

    parameter_count = len(distribution.get_param_names())
    assert len(closed) == 2 * parameter_count
    assert pair_plot.call_count == parameter_count
    assert all(str(tmp_path) in filename for filename in closed)
    output = capsys.readouterr().out
    assert "DISTRIBUTION OF PARAMETERS" in output
    assert "OBJECTIVE FUNCTION" in output
    assert "PARAMETERS" in output


def test_prior_and_concentration_diagnostics_route_overlays(monkeypatch) -> None:
    distribution = _sample_table()
    comparison = _sample_table(offset=0.01)
    reference = build_lpm("ig")
    prior_grids = {
        name: np.column_stack(
            (
                np.linspace(*reference.get_calibration_range(name), 101),
                np.ones(101),
            )
        )
        for name in distribution.get_param_names()
    }
    prior = SimpleNamespace(density_grid=lambda name: prior_grids[name])
    close = Mock(side_effect=lambda *_args, **_kwargs: plt.close())
    pair_plot = Mock()
    monkeypatch.setattr(sample_diagnostics.plotting, "finalize_figure", close)
    monkeypatch.setattr(
        sample_diagnostics.plotting,
        "plot_histogram_scatter",
        pair_plot,
    )

    sample_diagnostics.plot_prior_comparison(
        distribution,
        lpm_reference=reference,
        lpm_2nd=comparison,
        lpm_2nd_method="comparison",
        directory="figures",
        prior=prior,
    )
    sample_diagnostics.plot_concentration_diagnostics(
        distribution,
        self_method="MH",
        concentrations_reference=SimpleNamespace(
            frame=pd.DataFrame({"concentration": [1.0, 2.0]})
        ),
        lpm_2nd=comparison,
        lpm_2nd_method="comparison",
        directory="figures",
    )

    assert close.call_count == len(distribution.get_param_names())
    assert pair_plot.call_count == len(distribution.get_concentration_names())


def test_parameter_diagnostics_render_and_close_shared_figures(tmp_path) -> None:
    distribution = _sample_table()
    comparison = _sample_table(offset=0.01)
    reference = build_lpm("ig")
    names = distribution.get_param_names()
    plt.close("all")

    sample_diagnostics.plot_parameter_diagnostics(
        distribution,
        self_method="MH",
        lpm_reference=reference,
        lpm_2nd=comparison,
        lpm_2nd_method="comparison",
        directory=tmp_path,
    )

    expected = {
        *(f"comp_{name}.png" for name in names),
        *(f"objfunction_{name}.png" for name in names),
        *(
            f"comp2D_{name}_{names[(index + 1) % len(names)]}.png"
            for index, name in enumerate(names)
        ),
    }
    assert {path.name for path in tmp_path.glob("*.png")} == expected
    assert plt.get_fignums() == []


def test_parameter_helpers_filter_nonfinite_values_and_invalid_bins() -> None:
    distribution = _sample_table()
    name = distribution.get_param_names()[0]
    distribution.frame.loc[1, name] = np.nan
    distribution.frame.loc[2, name] = np.inf

    assert sample_diagnostics._finite_parameter_values(distribution, name).size == 2

    invalid_model = SimpleNamespace(
        get_calibration_range_width=lambda _name: 0.0,
        get_calibration_range=lambda _name: (0.0, 0.0),
    )
    invalid_distribution = SimpleNamespace(lpm_template=invalid_model)
    bins = sample_diagnostics._parameter_bins(
        invalid_distribution, "mu", np.array([1.0, 2.0])
    )
    assert bins.size == 0


def test_empty_parameter_and_concentration_tables_are_safe(monkeypatch) -> None:
    distribution = _sample_table()
    name = distribution.get_param_names()[0]
    distribution.frame.loc[:, name] = np.nan
    create_figure = Mock()
    pair_plot = Mock()
    monkeypatch.setattr(
        sample_diagnostics.plotting,
        "create_figure",
        create_figure,
    )
    monkeypatch.setattr(
        sample_diagnostics.plotting,
        "plot_histogram_scatter",
        pair_plot,
    )

    sample_diagnostics._plot_param_histogram(
        distribution, name, "MH", None, None, "", None
    )
    empty_concentrations = LpmSampleTable(build_lpm("exp"), c_names=[])
    sample_diagnostics.plot_concentration_diagnostics(empty_concentrations)

    create_figure.assert_not_called()
    pair_plot.assert_not_called()
