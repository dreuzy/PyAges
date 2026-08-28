# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Plotting boundary for systematic parameter-space exploration.

One-dimensional objectives are drawn as lines. Higher-dimensional grids are
shown through pairwise central slices so plotting remains bounded as the number
of LPM parameters grows. Reachable concentrations use pairwise projections of
the ordered tracer/date columns.
"""

from __future__ import annotations

from itertools import combinations, islice
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

import pyages._plotting as plotting
from pyages.calibration.exploration.grid import ParameterGrid
from pyages.config.runtime import DisplayOptions
from pyages.lpm.plotting.sample_diagnostics import plot_parameter_pair


def _finish(display: DisplayOptions, figure: Figure, name: str) -> None:
    """Apply the shared save/close policy to one completed figure."""
    filename = None
    if display.figure_save and display.directory is not None:
        filename = Path(display.directory) / name
    plotting.finalize_figure(figure, filename, close=display.figure_close)


def _plot_line(
    axis: np.ndarray,
    values: np.ndarray,
    name: str,
    parameter_name: str,
    display: DisplayOptions,
    results=None,
) -> None:
    """Plot a one-parameter objective profile and calibrated samples."""
    figure, plot = plotting.create_figure(x_label=parameter_name, title=name)
    plot.plot(axis, values)
    plot.set_yscale("log")
    if results is not None:
        plot_parameter_pair(results, parameter_name, "obj_function", axis=plot)
    _finish(display, figure, name)


def _plot_surface(
    x: np.ndarray,
    y: np.ndarray,
    values: np.ndarray,
    name: str,
    x_name: str,
    y_name: str,
    display: DisplayOptions,
    results=None,
) -> None:
    """Plot one two-parameter objective slice and calibrated samples."""
    figure, plot = plotting.create_figure(
        x_label=x_name,
        y_label=y_name,
        title=name,
    )
    image = plot.pcolormesh(x, y, values.T, cmap=plotting.white_low_colormap())
    figure.colorbar(image, ax=plot)
    if results is not None:
        plot_parameter_pair(results, x_name, y_name, axis=plot)
    _finish(display, figure, name)


def plot_parameter_grid(
    grid: ParameterGrid,
    values: np.ndarray,
    display: DisplayOptions,
    *,
    name: str,
    results=None,
) -> None:
    """Plot a one-dimensional grid or central pairwise slices."""
    if not display.figure:
        return
    if len(grid.axes) == 1:
        _plot_line(grid.axes[0], values, name, grid.names[0], display, results=results)
        return

    for x_index, y_index in combinations(range(len(grid.axes)), 2):
        # Non-plotted dimensions stay at their central grid index. This is a
        # slice through the objective, not a marginalization or projection.
        selectors: list[int | slice] = [len(axis) // 2 for axis in grid.axes]
        selectors[x_index] = slice(None)
        selectors[y_index] = slice(None)
        surface = values[tuple(selectors)]
        suffix = "" if len(grid.axes) == 2 else f"_{x_index}_{y_index}"
        _plot_surface(
            grid.axes[x_index],
            grid.axes[y_index],
            surface,
            name + suffix,
            grid.names[x_index],
            grid.names[y_index],
            display,
            results=results,
        )


def plot_reachable_concentrations(
    concentrations: pd.DataFrame,
    display: DisplayOptions,
    *,
    observations=None,
    maximum: int = 10,
) -> None:
    """Plot the first pairwise projections of reachable concentrations.

    ``maximum`` limits figure count, not the number of modeled grid rows.
    Observation points are overlaid only when a compatible table is supplied.
    """
    if not display.figure:
        return
    pairs = islice(combinations(range(len(concentrations.columns)), 2), maximum)
    for first, second in pairs:
        first_name = str(concentrations.columns[first])
        second_name = str(concentrations.columns[second])
        name = f"reachable_{first_name}_{second_name}"
        figure, plot = plotting.create_figure(
            x_label=first_name,
            y_label=second_name,
            title=name,
        )
        plot.scatter(
            concentrations.iloc[:, first],
            concentrations.iloc[:, second],
            marker="+",
            c="b",
            s=10,
        )
        if observations is not None:
            observations.plot_pair(first, second)
        _finish(display, figure, name)


__all__ = ["plot_parameter_grid", "plot_reachable_concentrations"]
