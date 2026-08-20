"""Plotting helpers for systematic parameter exploration."""

from __future__ import annotations

from itertools import combinations, islice

import numpy as np
import pandas as pd

import pyage.tools.figures_additional as figures
from pyage.calibration.utils.parameter_grid import ParameterGrid
from pyage.config.runtime import DisplayOptions


def _finish(display: DisplayOptions, name: str) -> None:
    display.figure_close_fx(name)


def _plot_line(
    axis: np.ndarray,
    values: np.ndarray,
    name: str,
    parameter_name: str,
    display: DisplayOptions,
    results=None,
) -> None:
    _, plot = figures.figure_init(xlab=parameter_name, figname=name)
    plot.plot(axis, values)
    plot.set_yscale("log")
    if results is not None:
        results.display_param_vs_param(parameter_name, "obj_function")
    _finish(display, name)


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
    figure, plot = figures.figure_init(xlab=x_name, ylab=y_name, figname=name)
    image = plot.pcolormesh(x, y, values.T, cmap=figures.cmap_white_jet())
    figure.colorbar(image, ax=plot)
    if results is not None:
        results.display_param_vs_param(x_name, y_name)
    _finish(display, name)


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
    """Plot the first pairwise projections of reachable concentrations."""
    if not display.figure:
        return
    pairs = islice(combinations(range(len(concentrations.columns)), 2), maximum)
    for first, second in pairs:
        first_name = str(concentrations.columns[first])
        second_name = str(concentrations.columns[second])
        name = f"reachable_{first_name}_{second_name}"
        _, plot = figures.figure_init(
            xlab=first_name,
            ylab=second_name,
            figname=name,
        )
        plot.scatter(
            concentrations.iloc[:, first],
            concentrations.iloc[:, second],
            marker="+",
            c="b",
            s=10,
        )
        if observations is not None:
            observations.figure_concentrations(first, second)
        _finish(display, name)


__all__ = ["plot_parameter_grid", "plot_reachable_concentrations"]
