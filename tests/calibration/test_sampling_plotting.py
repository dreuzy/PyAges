# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Selection and projection contracts for systematic-sampling plots."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd

from pyages.calibration.utils import sampling_plotting
from pyages.calibration.utils.parameter_grid import ParameterGrid


def test_parameter_grid_plot_is_disabled_without_figure_output(monkeypatch) -> None:
    line = Mock()
    surface = Mock()
    monkeypatch.setattr(sampling_plotting, "_plot_line", line)
    monkeypatch.setattr(sampling_plotting, "_plot_surface", surface)
    grid = ParameterGrid([0.0], [1.0], target_size=2, names=["mu"])

    sampling_plotting.plot_parameter_grid(
        grid,
        np.zeros(grid.shape),
        SimpleNamespace(figure=False),
        name="objective",
    )

    line.assert_not_called()
    surface.assert_not_called()


def test_parameter_grid_plot_dispatches_one_dimensional_line(monkeypatch) -> None:
    line = Mock()
    monkeypatch.setattr(sampling_plotting, "_plot_line", line)
    grid = ParameterGrid([0.0], [1.0], target_size=2, names=["mu"])
    values = np.arange(grid.size, dtype=float)
    display = SimpleNamespace(figure=True)

    sampling_plotting.plot_parameter_grid(
        grid, values, display, name="objective", results="posterior"
    )

    line.assert_called_once_with(
        grid.axes[0],
        values,
        "objective",
        "mu",
        display,
        results="posterior",
    )


def test_parameter_grid_plot_uses_central_pairwise_slices(monkeypatch) -> None:
    surface = Mock()
    monkeypatch.setattr(sampling_plotting, "_plot_surface", surface)
    grid = ParameterGrid(
        [0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0],
        target_size=8,
        names=["a", "b", "c"],
    )
    values = np.arange(grid.size, dtype=float).reshape(grid.shape)

    sampling_plotting.plot_parameter_grid(
        grid,
        values,
        SimpleNamespace(figure=True),
        name="objective",
    )

    assert surface.call_count == 3
    assert [call.args[3] for call in surface.call_args_list] == [
        "objective_0_1",
        "objective_0_2",
        "objective_1_2",
    ]
    assert np.array_equal(
        surface.call_args_list[0].args[2], values[:, :, len(grid.axes[2]) // 2]
    )


def test_reachable_concentration_plot_respects_pair_limit_and_observations(
    monkeypatch,
) -> None:
    axis = Mock()
    monkeypatch.setattr(
        sampling_plotting.figures,
        "figure_init",
        lambda **_kwargs: (object(), axis),
    )
    observations = SimpleNamespace(plot_pair=Mock())
    display = SimpleNamespace(figure=True, figure_close_fx=Mock())
    concentrations = pd.DataFrame(
        {
            "cfc11": [1.0, 2.0],
            "cfc12": [3.0, 4.0],
            "sf6": [5.0, 6.0],
        }
    )

    sampling_plotting.plot_reachable_concentrations(
        concentrations,
        display,
        observations=observations,
        maximum=2,
    )

    assert axis.scatter.call_count == 2
    assert observations.plot_pair.call_args_list[0].args == (0, 1)
    assert observations.plot_pair.call_args_list[1].args == (0, 2)
    assert display.figure_close_fx.call_count == 2
