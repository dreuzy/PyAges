# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Shared styles and data helpers for workflow figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.tri import TriAnalyzer, Triangulation

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


def _ensure_frame(result) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result.copy()
    if hasattr(result, "frame"):
        return result.frame.copy()
    raise TypeError("Expected a pandas DataFrame or an object exposing .frame.")


def _best_row(frame: pd.DataFrame) -> pd.Series | None:
    if frame.empty:
        return None
    if "obj_function" in frame.columns:
        values = pd.to_numeric(frame["obj_function"], errors="coerce")
        if not values.isna().all():
            return frame.loc[values.idxmin()].copy()
    return frame.iloc[0].copy()


def _method_color(method_name: str, index: int) -> str:
    if method_name in DEFAULT_METHOD_COLORS:
        return DEFAULT_METHOD_COLORS[method_name]
    fallback = plt.get_cmap("tab10")
    return fallback(index % 10)


def _pretty_tracer_name(name: str) -> str:
    lower = name.lower()
    if lower.startswith("cfc"):
        return name.upper()
    if lower == "sf6":
        return "SF6"
    return name


def _axis_label(tracer: str, unit: str | None) -> str:
    label = _pretty_tracer_name(tracer)
    if unit:
        return f"{label} [{unit}]"
    return label


def _reachable_column_name(tracer: str, date_value: float) -> str:
    return f"{tracer}-{date_value:.1f}".replace(".", "_")


def _save_figure(fig, filename: str | Path | None, dpi: int = 220):
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


def _reference_concentration_lookup(reference_concentrations):
    if reference_concentrations is None:
        return None
    if hasattr(reference_concentrations, "cv"):
        frame = reference_concentrations.cv.copy()
    elif isinstance(reference_concentrations, pd.DataFrame):
        frame = reference_concentrations.copy()
    else:
        raise TypeError("reference_concentrations must be a DataFrame or expose .cv")
    required = {"element", "date", "concentration"}
    if not required.issubset(frame.columns):
        raise ValueError(
            "reference_concentrations must contain 'element', 'date' and 'concentration' columns."
        )
    return frame.set_index(["element", "date"])["concentration"]


def _nearest_reference_objective_row(
    objective_frame: pd.DataFrame,
    reference_params: dict[str, float] | None,
    param_names: list[str],
):
    if not reference_params:
        return None
    available = [
        name
        for name in param_names
        if name in reference_params and name in objective_frame.columns
    ]
    if not available:
        return None
    numeric = objective_frame[available].apply(pd.to_numeric, errors="coerce")
    valid = numeric.notna().all(axis=1)
    if not valid.any():
        return None
    ref = np.array([float(reference_params[name]) for name in available], dtype=float)
    distances = ((numeric.loc[valid].to_numpy(dtype=float) - ref) ** 2).sum(axis=1)
    nearest_index = numeric.loc[valid].index[int(np.argmin(distances))]
    return objective_frame.loc[nearest_index]
