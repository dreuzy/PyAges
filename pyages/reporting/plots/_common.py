# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file centralizes conventions shared by scientific report figures.

"""Provide consistent colors, labels, data adapters, and figure finalization.

Reporting functions use these helpers to extract pandas frames from supported
result objects, identify best samples, choose stable method colors, and format
tracer names with their units. Objective plots also share interpolation and
reference-location routines so their visual layers have the same meaning.

The save helper writes a figure only when a filename is supplied and otherwise
returns the live Matplotlib object to the caller. Keeping these conventions here
prevents individual reports from silently assigning different semantics to the
same marker or color.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast, runtime_checkable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.tri import TriAnalyzer, Triangulation
from matplotlib.typing import ColorType

from pyages.concentrations._labels import pretty_tracer_name
from pyages.concentrations.schema import OBSERVATION_KEY_COLUMN, observation_key

DEFAULT_METHOD_COLORS = {
    "Metropolis_Hastings": "#1f77b4",
    "forward_uncertainty_quantification": "#ff7f0e",
}
REACHABLE_COLOR = "#d9e2e8"
OBSERVED_COLOR = "#111111"
MEDIAN_COLOR = "#08519c"
SINGLE_DATE_HIGHLIGHT_COLOR = "#d62728"
INTERVAL_50_COLOR = "#6baed6"
INTERVAL_90_COLOR = "#c6dbef"
GRID_CMAP = "cividis_r"


@runtime_checkable
class _FrameProvider(Protocol):
    """Object exposing the result frame consumed by plotting functions."""

    @property
    def frame(self) -> pd.DataFrame:
        """Return the tabular result data."""
        ...


type FrameSource = pd.DataFrame | _FrameProvider


def apply_example_style() -> None:
    """Apply a lighter plotting style for didactic example figures."""
    plt.rcParams.update(
        {
            "figure.figsize": (7.0, 4.5),
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "axes.titleweight": "semibold",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "--",
            "legend.fontsize": 11,
            "legend.frameon": False,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _ensure_frame(result: FrameSource) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result.copy()
    if isinstance(result, _FrameProvider):
        return result.frame.copy()
    raise TypeError("Expected a pandas DataFrame or an object exposing .frame.")


def _best_row(frame: pd.DataFrame) -> pd.Series | None:
    if frame.empty:
        return None
    if "obj_function" in frame.columns:
        objective = frame["obj_function"]
        if not isinstance(objective, pd.Series):
            raise ValueError("Result frame must contain one 'obj_function' column")
        values = np.asarray(pd.to_numeric(objective, errors="coerce"), dtype=float)
        finite_positions = np.flatnonzero(np.isfinite(values))
        if finite_positions.size:
            best_position = finite_positions[int(np.argmin(values[finite_positions]))]
            return cast(pd.Series, frame.iloc[best_position].copy())
    return cast(pd.Series, frame.iloc[0].copy())


def _method_color(method_name: str, index: int) -> ColorType:
    if method_name in DEFAULT_METHOD_COLORS:
        return DEFAULT_METHOD_COLORS[method_name]
    fallback = plt.get_cmap("tab10")
    return fallback(index % 10)


def _axis_label(tracer: str, unit: str | None) -> str:
    label = pretty_tracer_name(tracer)
    if unit:
        return f"{label} [{unit}]"
    return label


def _save_figure(
    fig: Figure,
    filename: str | Path | None,
    dpi: int = 220,
) -> Figure:
    if filename is not None:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return fig


def _plot_interpolated_objective_surface(ax, x, y, values, vmin: float, vmax: float):
    """Plot a smooth objective background when triangulation is feasible."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & np.isfinite(values)
    x = x[valid]
    y = y[valid]
    values = values[valid]

    if len(x) < 3 or len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return ax.scatter(
            x,
            y,
            c=values,
            s=18,
            cmap=GRID_CMAP,
            vmin=vmin,
            vmax=vmax,
            alpha=0.25,
            edgecolors="none",
            zorder=1,
        )

    try:
        triangulation = Triangulation(x, y)
        mask = TriAnalyzer(triangulation).get_flat_tri_mask(min_circle_ratio=0.01)
        triangulation.set_mask(mask)
        levels = np.linspace(vmin, vmax, 28)
        return ax.tricontourf(
            triangulation,
            values,
            levels=levels,
            cmap=GRID_CMAP,
            alpha=0.92,
            extend="both",
        )
    except Exception:
        return ax.scatter(
            x,
            y,
            c=values,
            s=18,
            cmap=GRID_CMAP,
            vmin=vmin,
            vmax=vmax,
            alpha=0.25,
            edgecolors="none",
            zorder=1,
        )


def _reference_concentration_lookup(
    reference_concentrations: FrameSource | None,
) -> pd.Series | None:
    """Index reference rows by explicit or position-derived observation keys."""
    if reference_concentrations is None:
        return None
    frame = _ensure_frame(reference_concentrations)
    required = {"concentration"}
    if OBSERVATION_KEY_COLUMN not in frame.columns:
        required.update(("element", "date"))
    if not required.issubset(frame.columns):
        raise ValueError(
            "reference_concentrations must contain 'concentration' and either "
            "'observation_key' or both 'element' and 'date' columns"
        )
    if frame.columns.duplicated().any():
        raise ValueError("reference_concentrations must contain unique columns")
    concentrations = frame["concentration"]
    if not isinstance(concentrations, pd.Series):
        raise ValueError(
            "reference_concentrations must contain one concentration column"
        )
    if OBSERVATION_KEY_COLUMN in frame.columns:
        explicit_keys = frame[OBSERVATION_KEY_COLUMN]
        if (
            not isinstance(explicit_keys, pd.Series)
            or not explicit_keys.map(
                lambda value: isinstance(value, str) and bool(value.strip())
            ).all()
        ):
            raise ValueError(
                "reference observation_key values must be non-empty strings"
            )
        keys = explicit_keys.str.strip().tolist()
    else:
        elements = frame["element"]
        dates = frame["date"]
        if not isinstance(elements, pd.Series) or not isinstance(dates, pd.Series):
            raise ValueError(
                "reference_concentrations must contain one element and one date column"
            )
        keys = [
            observation_key(str(element), float(date), index)
            for index, (element, date) in enumerate(
                zip(
                    elements.to_numpy(copy=False),
                    dates.to_numpy(copy=False),
                    strict=True,
                )
            )
        ]
    if pd.Index(keys).has_duplicates:
        raise ValueError("reference observation_key values must be unique")
    return pd.Series(
        concentrations.to_numpy(copy=True),
        index=keys,
        name="concentration",
    )


def _nearest_reference_objective_row(
    objective_frame: pd.DataFrame,
    reference_params: dict[str, float] | None,
    param_names: list[str],
) -> pd.Series | None:
    """Return the objective-grid row nearest to available reference parameters.

    Distance is the unscaled squared Euclidean distance in the parameter columns
    shared by ``param_names``, ``reference_params``, and ``objective_frame``.
    Rows with non-numeric coordinates are excluded. If no reference coordinate
    or no valid row remains, ``None`` is returned; equal distances retain the
    first grid row selected by NumPy.

    The returned objective value is an approximation at the existing grid point,
    not an interpolation at the exact reference parameters. Parameters with very
    different numerical scales can therefore dominate this visual marker.
    """

    if not reference_params:
        return None
    # Partial references are useful for plotting, but the distance must use the
    # same ordered subset for the grid matrix and reference vector.
    available = [
        name
        for name in param_names
        if name in reference_params and name in objective_frame.columns
    ]
    if not available:
        return None
    numeric = objective_frame[available].apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype=float)
    valid = np.all(np.isfinite(values), axis=1)
    if not np.any(valid):
        return None
    ref = np.array([float(reference_params[name]) for name in available], dtype=float)
    valid_positions = np.flatnonzero(valid)
    distances = ((values[valid] - ref) ** 2).sum(axis=1)
    nearest_position = valid_positions[int(np.argmin(distances))]
    return cast(pd.Series, objective_frame.iloc[nearest_position].copy())
