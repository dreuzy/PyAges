# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file provides low-level Matplotlib helpers shared across PyAges.

"""Create, combine, and finalize the basic figures used by higher-level modules.

The helpers centralize common figure labels and sizing, construction of the
white-to-color map used for objective surfaces, and the save-or-show boundary.
They also provide a histogram-plus-scatter diagnostic that filters non-finite
pairs before plotting and can add independent reference coordinates.

This private module knows only about numeric arrays, axes, and output paths. It
does not interpret calibration objects or perform scientific calculations.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from matplotlib.axes import Axes
from matplotlib.colors import Colormap, ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch


def create_figure(
    x_label: str | None = None,
    y_label: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (6.0, 4.0),
) -> tuple[Figure, Axes]:
    """Create a consistently styled figure and axis."""
    figure, axis = plt.subplots(figsize=figsize)
    if x_label is not None:
        axis.set_xlabel(x_label, fontsize=16, fontweight="bold")
    if y_label is not None:
        axis.set_ylabel(y_label, fontsize=14, fontweight="bold")
    if title is not None:
        axis.set_title(title, fontsize=22, fontweight="bold")
    axis.tick_params(axis="both", labelsize=14)
    axis.grid(True)
    return figure, axis


def finalize_figure(
    figure: Figure,
    filename: str | Path | None = None,
    *,
    close: bool = True,
    dpi: int = 300,
) -> Path | None:
    """Save ``figure`` when requested and optionally close that exact figure."""
    output = None if filename is None else Path(filename)
    if output is not None:
        requested_format = output.suffix.removeprefix(".").lower()
        supported_formats = figure.canvas.get_supported_filetypes()
        if requested_format not in supported_formats:
            output = Path(f"{output}.{mpl.rcParams['savefig.format']}")

    try:
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(output, dpi=dpi)
    finally:
        if close:
            plt.close(figure)
    return output


def white_low_colormap(
    base: str | Colormap = "cividis",
    *,
    fade_samples: int = 64,
    color_samples: int = 256,
) -> ListedColormap:
    """Return a colormap whose lowest values fade from white.

    ``cividis`` is the perceptually uniform default. Reproduction scripts may
    explicitly request ``base="jet"`` when matching a qualified legacy figure.
    """
    if fade_samples <= 0 or color_samples <= 0:
        raise ValueError("fade_samples and color_samples must be positive")

    try:
        base_colormap = mpl.colormaps[base] if isinstance(base, str) else base
    except KeyError as error:
        raise ValueError(f"Unknown Matplotlib colormap: {base!r}") from error

    colors = base_colormap(np.linspace(0.0, 1.0, color_samples))
    fade = np.ones((fade_samples, 4))
    fade[:, :3] = np.linspace(np.ones(3), colors[0, :3], fade_samples)
    name = f"pyages_white_{base_colormap.name}"
    return ListedColormap(np.vstack((fade, colors)), name=name)


def _finite_pairs(
    x: npt.ArrayLike | None,
    y: npt.ArrayLike | None,
    *,
    layer: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]] | None:
    if x is None and y is None:
        return None
    if x is None or y is None:
        raise ValueError(f"{layer}_x and {layer}_y must be provided together")

    x_values = np.asarray(x, dtype=float).reshape(-1)
    y_values = np.asarray(y, dtype=float).reshape(-1)
    if x_values.size != y_values.size:
        raise ValueError(f"{layer}_x and {layer}_y must have the same length")
    finite = np.isfinite(x_values) & np.isfinite(y_values)
    return x_values[finite], y_values[finite]


def plot_histogram_scatter(
    *,
    histogram_x: npt.ArrayLike | None = None,
    histogram_y: npt.ArrayLike | None = None,
    histogram_label: str = "",
    scatter_x: npt.ArrayLike | None = None,
    scatter_y: npt.ArrayLike | None = None,
    scatter_label: str = "",
    reference_x: float | None = None,
    reference_y: float | None = None,
    reference_label: str = "",
    x_label: str | None = None,
    y_label: str | None = None,
    title: str | None = None,
    filename: str | Path | None = None,
) -> tuple[Figure, Axes]:
    """Combine an optional density cloud, sample points, and reference point.

    Each layer is supplied as an X/Y pair. Providing only one coordinate raises
    ``ValueError``; paired non-finite coordinates are removed before rendering.
    ``histogram_*`` values form a two-dimensional histogram with a color bar,
    ``scatter_*`` values remain individual red crosses, and a finite
    ``reference_*`` pair is drawn as a larger point.

    Labels are added to the legend only for layers that are both present and
    named. A new figure and axis are always created and returned. When
    ``filename`` is supplied, normal figure finalization also saves the image.
    """
    histogram = _finite_pairs(histogram_x, histogram_y, layer="histogram")
    scatter = _finite_pairs(scatter_x, scatter_y, layer="scatter")
    if (reference_x is None) != (reference_y is None):
        raise ValueError("reference_x and reference_y must be provided together")

    figure, axis = create_figure(x_label=x_label, y_label=y_label, title=title)
    legend_handles = []

    if histogram is not None and histogram[0].size:
        colormap = white_low_colormap()
        image = axis.hist2d(*histogram, bins=50, cmap=colormap)[3]
        figure.colorbar(image, ax=axis)
        if histogram_label:
            legend_handles.append(Patch(facecolor=colormap(0.7), label=histogram_label))

    if scatter is not None and scatter[0].size:
        points = axis.scatter(
            *scatter,
            marker="+",
            c="red",
            s=40,
            label=scatter_label or None,
        )
        if scatter_label:
            legend_handles.append(points)

    reference_is_finite = (
        reference_x is not None
        and reference_y is not None
        and np.isfinite(reference_x)
        and np.isfinite(reference_y)
    )
    if reference_is_finite:
        reference = axis.scatter(
            reference_x,
            reference_y,
            marker="o",
            c="red",
            s=150,
            label=reference_label or None,
        )
        if reference_label:
            legend_handles.append(reference)

    if legend_handles:
        axis.legend(handles=legend_handles)

    if filename is not None:
        finalize_figure(figure, filename)
    return figure, axis


__all__ = [
    "create_figure",
    "finalize_figure",
    "plot_histogram_scatter",
    "white_low_colormap",
]
