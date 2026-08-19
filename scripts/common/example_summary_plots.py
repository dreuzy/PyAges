# -*- coding: utf-8 -*-
"""
Compact, didactic plots for the example workflows.
"""

from __future__ import annotations

from itertools import combinations
from math import ceil
from pathlib import Path
import re

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from matplotlib.tri import TriAnalyzer, Triangulation
import numpy as np
import pandas as pd

import pyage.convolution.convolution_tracers as convolution_tracers


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
    if hasattr(result, "dist"):
        return result.dist().copy()
    raise TypeError("Expected a pandas DataFrame or an object exposing dist().")


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


def _pretty_label_from_column(name: str) -> str:
    match = re.match(r"^(?P<tracer>.+)_(?P<date>\d+(?:\.\d+)?)_\d+$", name)
    if match:
        tracer = _pretty_tracer_name(match.group("tracer"))
        return f"{tracer} ({float(match.group('date')):.2f})"
    return _pretty_tracer_name(name)


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


def plot_observations_overview(
    cdata,
    filename: str | Path | None = None,
    title: str = "Observed concentrations",
    highlight_dates: list[float] | None = None,
    highlight_label: str = "Single-date interpretation",
    highlight_tolerance: float = 0.02,
):
    """
    Plot observation-only panels for each tracer.
    """
    apply_example_style()
    df = cdata.cv.copy()
    tracers = list(dict.fromkeys(df["element"].tolist()))
    ncols = 2 if len(tracers) == 4 else min(3, max(len(tracers), 1))
    nrows = ceil(max(len(tracers), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(6.2 * ncols, 3.8 * nrows), squeeze=False)
    highlight_array = np.asarray(highlight_dates or [], dtype=float)
    highlighted_any = False

    for ax, tracer in zip(axs.flatten(), tracers):
        tracer_df = df[df["element"] == tracer].sort_values("date")
        has_error = "error" in tracer_df.columns and np.any(pd.to_numeric(tracer_df["error"], errors="coerce") > 0)
        yerr = tracer_df["error"] if has_error else None
        ax.errorbar(
            tracer_df["date"],
            tracer_df["concentration"],
            yerr=yerr,
            fmt="o",
            ms=5,
            color=MEDIAN_COLOR,
            ecolor="#9ecae1",
            elinewidth=1.2,
            capsize=2,
        )
        if highlight_array.size:
            dates = pd.to_numeric(tracer_df["date"], errors="coerce").to_numpy(dtype=float)
            highlight_mask = np.any(
                np.isclose(
                    dates[:, None],
                    highlight_array[None, :],
                    atol=float(highlight_tolerance),
                    rtol=0.0,
                ),
                axis=1,
            )
            if highlight_mask.any():
                highlighted_any = True
                highlight_df = tracer_df.loc[highlight_mask]
                highlight_yerr = yerr.loc[highlight_df.index] if has_error else None
                ax.errorbar(
                    highlight_df["date"],
                    highlight_df["concentration"],
                    yerr=highlight_yerr,
                    fmt="o",
                    ms=6.5,
                    color=SINGLE_DATE_HIGHLIGHT_COLOR,
                    ecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                    elinewidth=1.4,
                    capsize=2,
                    markeredgecolor="white",
                    markeredgewidth=0.7,
                    zorder=4,
                )
        unit = tracer_df["unit"].iloc[0] if "unit" in tracer_df.columns and not tracer_df.empty else None
        ax.set_title(_pretty_tracer_name(tracer))
        ax.set_xlabel("Year")
        ax.set_ylabel(_axis_label(tracer, unit))

    for ax in axs.flatten()[len(tracers):]:
        ax.remove()

    if highlighted_any:
        fig.legend(
            handles=[
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markersize=6,
                    markerfacecolor=MEDIAN_COLOR,
                    markeredgecolor=MEDIAN_COLOR,
                    label="Temporal observations",
                ),
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markersize=7,
                    markerfacecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                    markeredgecolor="white",
                    label=highlight_label,
                ),
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=2,
        )
    fig.suptitle(title, fontsize=15, y=1.08 if highlighted_any else 1.04)
    fig.tight_layout(rect=(0, 0, 1, 0.91 if highlighted_any else 0.96))
    return _save_figure(fig, filename)


def plot_single_date_model_space(
    concentration_sampled,
    reachable_frame: pd.DataFrame,
    posterior_results: dict[str, object],
    reference_concentrations=None,
    reference_label: str = "Reference model",
    filename: str | Path | None = None,
    title: str = "Observed concentrations, reachable space and calibrated models",
):
    """
    Plot pairwise concentration panels for the single-date example.
    """
    apply_example_style()
    observed = concentration_sampled.cv.reset_index(drop=True)
    reference_lookup = _reference_concentration_lookup(reference_concentrations)
    concentration_columns = concentration_sampled.names_dates()
    reachable_columns = [
        _reachable_column_name(row["element"], float(row["date"]))
        for _, row in observed.iterrows()
    ]
    pairs = list(combinations(range(len(concentration_columns)), 2))
    if not pairs:
        raise ValueError("At least two tracers are required to plot model space.")
    if len(concentration_columns) >= 4:
        pairs = pairs[:4]

    ncols = 2 if len(pairs) >= 4 else len(pairs)
    nrows = ceil(len(pairs) / ncols)
    fig, axs = plt.subplots(
        nrows,
        ncols,
        figsize=(5.4 * ncols, 4.6 * nrows),
        squeeze=False,
    )
    axs = axs.flatten()

    for ax_index, ((i0, i1), ax) in enumerate(zip(pairs, axs)):
        xcol = concentration_columns[i0]
        ycol = concentration_columns[i1]
        xcol_reach = reachable_columns[i0]
        ycol_reach = reachable_columns[i1]
        ax.scatter(
            reachable_frame[xcol_reach],
            reachable_frame[ycol_reach],
            s=16,
            alpha=0.35,
            color=REACHABLE_COLOR,
            edgecolors="none",
            label="Prior reachable space" if ax_index == 0 else None,
        )

        for method_index, (method_name, result) in enumerate(posterior_results.items()):
            frame = _ensure_frame(result)
            if xcol not in frame.columns or ycol not in frame.columns:
                continue
            color = _method_color(method_name, method_index)
            sample = frame[[xcol, ycol]].dropna()
            if len(sample) > 450:
                sample = sample.sample(450, random_state=12345)
            ax.scatter(
                sample[xcol],
                sample[ycol],
                s=20,
                alpha=0.18,
                color=color,
                linewidths=0,
                label=f"{method_name} posterior samples" if ax_index == 0 else None,
            )
            best = _best_row(frame)
            if best is not None:
                ax.scatter(
                    best[xcol],
                    best[ycol],
                    marker="*",
                    s=150,
                    color=color,
                    edgecolor="white",
                    linewidth=0.8,
                    label=f"{method_name} posterior best" if ax_index == 0 else None,
                    zorder=4,
                )

        ax.scatter(
            observed.loc[i0, "concentration"],
            observed.loc[i1, "concentration"],
            marker="o",
            s=90,
            color=OBSERVED_COLOR,
            edgecolor="white",
            linewidth=0.8,
            label="Observation" if ax_index == 0 else None,
            zorder=5,
        )
        if reference_lookup is not None:
            xkey = (observed.loc[i0, "element"], observed.loc[i0, "date"])
            ykey = (observed.loc[i1, "element"], observed.loc[i1, "date"])
            if xkey in reference_lookup.index and ykey in reference_lookup.index:
                ax.scatter(
                    float(reference_lookup.loc[xkey]),
                    float(reference_lookup.loc[ykey]),
                    marker="D",
                    s=80,
                    color=MEDIAN_COLOR,
                    edgecolor="white",
                    linewidth=0.8,
                    label=reference_label if ax_index == 0 else None,
                    zorder=6,
                )
        ax.set_title(f"{_pretty_tracer_name(observed.loc[i0, 'element'])} vs {_pretty_tracer_name(observed.loc[i1, 'element'])}")
        ax.set_xlabel(_axis_label(observed.loc[i0, "element"], observed.loc[i0].get("unit")))
        ax.set_ylabel(_axis_label(observed.loc[i1, "element"], observed.loc[i1].get("unit")))

    for ax in axs[len(pairs):]:
        ax.remove()

    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 3))
    fig.suptitle(title, fontsize=15, y=1.08)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return _save_figure(fig, filename)


def plot_parameter_summary(
    results_by_method: dict[str, object],
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "Reference parameters",
    filename: str | Path | None = None,
    title: str = "Parameter distributions",
):
    """
    Plot a compact set of parameter histograms.
    """
    apply_example_style()
    ncols = min(3, max(len(param_names), 1))
    nrows = ceil(max(len(param_names), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(5.0 * ncols, 3.8 * nrows), squeeze=False)

    for ax, param_name in zip(axs.flatten(), param_names):
        for method_index, (method_name, result) in enumerate(results_by_method.items()):
            frame = _ensure_frame(result)
            if param_name not in frame.columns:
                continue
            color = _method_color(method_name, method_index)
            values = pd.to_numeric(frame[param_name], errors="coerce").dropna()
            if values.empty:
                continue
            bins = min(max(int(np.sqrt(len(values))), 12), 30)
            ax.hist(
                values,
                bins=bins,
                density=True,
                histtype="stepfilled" if method_index == 0 else "step",
                alpha=0.45 if method_index == 0 else 1.0,
                color=color,
                linewidth=1.8,
                label=f"{method_name} posterior",
            )
            best = _best_row(frame)
            if best is not None and param_name in best:
                ax.axvline(best[param_name], color=color, linestyle="--", linewidth=1.5)
        if reference_params and param_name in reference_params:
            ax.axvline(
                float(reference_params[param_name]),
                color=OBSERVED_COLOR,
                linestyle=":",
                linewidth=1.8,
                label=reference_label if ax is axs.flatten()[0] else None,
            )
        ax.set_title(param_name)
        ax.set_xlabel(param_name)
        ax.set_ylabel("Density")

    for ax in axs.flatten()[len(param_names):]:
        ax.remove()

    handles, labels = axs[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 3))
    fig.suptitle(title, fontsize=15, y=1.06)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return _save_figure(fig, filename)


def plot_parameter_distribution_comparison(
    distributions: dict[str, object],
    param_names: list[str],
    param_labels: dict[str, str] | None = None,
    param_density_labels: dict[str, str] | None = None,
    filename: str | Path | None = None,
    title: str | None = None,
):
    """
    Overlay posterior parameter distributions coming from different workflows.
    """
    apply_example_style()
    ncols = min(3, max(len(param_names), 1))
    nrows = ceil(max(len(param_names), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(5.2 * ncols, 3.9 * nrows), squeeze=False)

    color_cycle = plt.get_cmap("tab10")

    for ax, param_name in zip(axs.flatten(), param_names):
        for dist_index, (label, result) in enumerate(distributions.items()):
            frame = _ensure_frame(result)
            if param_name not in frame.columns:
                continue
            values = pd.to_numeric(frame[param_name], errors="coerce").dropna()
            if values.empty:
                continue
            bins = min(max(int(np.sqrt(len(values))), 12), 32)
            color = color_cycle(dist_index % 10)
            ax.hist(
                values,
                bins=bins,
                density=True,
                histtype="step",
                linewidth=2.0,
                color=color,
                alpha=0.95,
                label=label,
            )
            ax.axvline(values.median(), color=color, linestyle="--", linewidth=1.6, alpha=0.85)
        display_name = param_labels.get(param_name, param_name) if param_labels else param_name
        density_name = param_density_labels.get(param_name, display_name) if param_density_labels else display_name
        ax.set_title("")
        ax.set_xlabel(display_name, fontsize=18)
        ax.set_ylabel(f"$p({density_name})$", fontsize=18)
        ax.tick_params(axis="both", labelsize=16)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))

    for ax in axs.flatten()[len(param_names):]:
        ax.remove()

    handles, labels = axs[0, 0].get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            ncol=min(len(labels), 3),
            fontsize=13,
        )
    if title:
        fig.suptitle(title, fontsize=15, y=1.06)
        fig.tight_layout(rect=(0, 0, 1, 0.9))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save_figure(fig, filename)


def plot_temporal_fit_comparison(
    craw,
    posterior_frames: dict[str, pd.DataFrame],
    lpm_name: str,
    lpm_directory: str | Path,
    selection_modes: dict[str, str] | None = None,
    lpm_number: int = 40,
    filename: str | Path | None = None,
    title: str | None = None,
    start_year: float = 1960,
    highlight_dates: list[float] | None = None,
    highlight_label: str = "Single-date observation",
    highlight_tolerance: float = 0.02,
):
    """
    Overlay temporal fit summaries from multiple posterior distributions.
    """
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    from pyage.lpm.lpm_build import lpm_build
    from pyage.lpm.core.lpm_dist import LpmDist

    apply_example_style()
    tracer_names = list(dict.fromkeys(craw.cv["element"].tolist()))
    ncols = len(tracer_names) if len(tracer_names) <= 3 else 2
    nrows = ceil(max(len(tracer_names), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(6.5 * ncols, 4.2 * nrows), squeeze=False)
    highlight_array = np.asarray(highlight_dates or [], dtype=float)
    highlighted_any = False

    end_year = float(craw.cv["date"].max())
    tracers = convolution_tracers.ConvolutionTracers(
        names=craw.cv["element"].unique(),
        date=end_year,
    )

    overlay_styles = [
        {
            "band": "#c6dbef",
            "line": "#08519c",
            "band_label": "Transient 90% interval",
            "line_label": "Transient median",
        },
        {
            "band": "#fdd0a2",
            "line": "#d94801",
            "band_label": "Single-date 90% interval",
            "line_label": "Single-date median",
        },
        {
            "band": "#d9d9d9",
            "line": "#636363",
            "band_label": "Comparison 90% interval",
            "line_label": "Comparison median",
        },
    ]

    predictions: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
    for source_index, (label, frame) in enumerate(posterior_frames.items()):
        if frame.empty:
            continue
        mode = (selection_modes or {}).get(label, "random_line")
        lpm_template = lpm_build(lpm_name, directory_lpm=str(lpm_directory))
        lpm_dist = LpmDist(lpm_template, c_names=[])
        lpm_dist.fill_np_array(frame.to_numpy(), frame.columns.tolist())
        selection_mode = mode if mode in {"span", "successive", "span_full"} else "single_date"
        lpm_list, _, _ = lpm_dist.get_selection(
            lpm_number=lpm_number,
            time_span_mode=selection_mode,
            array_resolution=1000,
        )
        source_predictions: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for lpm in lpm_list:
            concentration_dict = tracers.convolve_date_range(lpm, start_year, end_year)
            for tracer_name, tracer_df in concentration_dict.items():
                ordered = tracer_df.sort_values("date")
                dates = ordered["date"].to_numpy(dtype=float)
                values = ordered["concentration"].to_numpy(dtype=float)
                if tracer_name not in source_predictions:
                    source_predictions[tracer_name] = (dates, values[None, :])
                else:
                    prev_dates, prev_values = source_predictions[tracer_name]
                    source_predictions[tracer_name] = (prev_dates, np.vstack([prev_values, values]))
        predictions[label] = source_predictions

    legend_handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color="#111111",
            markerfacecolor="#111111",
            markeredgecolor="#111111",
            markersize=6,
            label="Observations",
        )
    ]
    if highlight_array.size:
        legend_handles.append(
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color=SINGLE_DATE_HIGHLIGHT_COLOR,
                markerfacecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                markeredgecolor="white",
                markersize=7,
                label=highlight_label,
            )
        )

    for source_index, (label, source_predictions) in enumerate(predictions.items()):
        style = overlay_styles[min(source_index, len(overlay_styles) - 1)]
        legend_handles.append(Patch(facecolor=style["band"], edgecolor="none", alpha=0.75, label=style["band_label"]))
        legend_handles.append(Line2D([], [], color=style["line"], linewidth=2.4, label=style["line_label"]))
        for ax, tracer_name in zip(axs.flatten(), tracer_names):
            if tracer_name not in source_predictions:
                continue
            pred_dates, pred_array = source_predictions[tracer_name]
            q10, q50, q90 = np.quantile(pred_array, [0.10, 0.50, 0.90], axis=0)
            ax.fill_between(pred_dates, q10, q90, color=style["band"], alpha=0.55 if source_index else 0.75)
            ax.plot(pred_dates, q50, color=style["line"], linewidth=2.3)

    for ax, tracer_name in zip(axs.flatten(), tracer_names):
        observed = craw.cv[craw.cv["element"] == tracer_name].sort_values("date")
        unit = observed["unit"].iloc[0] if "unit" in observed.columns and not observed.empty else None
        has_error = "error" in observed.columns and np.any(pd.to_numeric(observed["error"], errors="coerce") > 0)
        error = observed["error"] if has_error else None
        ax.errorbar(
            observed["date"],
            observed["concentration"],
            yerr=error,
            fmt="o",
            color="#111111",
            ecolor="#4d4d4d",
            elinewidth=1.1,
            capsize=2,
            ms=5,
            zorder=5,
        )
        if highlight_array.size:
            observed_dates = pd.to_numeric(observed["date"], errors="coerce").to_numpy(dtype=float)
            highlight_mask = np.any(
                np.isclose(
                    observed_dates[:, None],
                    highlight_array[None, :],
                    atol=float(highlight_tolerance),
                    rtol=0.0,
                ),
                axis=1,
            )
            if highlight_mask.any():
                highlighted_any = True
                highlighted = observed.loc[highlight_mask]
                highlighted_error = error.loc[highlighted.index] if has_error else None
                ax.errorbar(
                    highlighted["date"],
                    highlighted["concentration"],
                    yerr=highlighted_error,
                    fmt="o",
                    color=SINGLE_DATE_HIGHLIGHT_COLOR,
                    ecolor=SINGLE_DATE_HIGHLIGHT_COLOR,
                    elinewidth=1.5,
                    capsize=2,
                    ms=6.5,
                    markeredgecolor="white",
                    markeredgewidth=0.8,
                    zorder=6,
                )
        ax.set_title("")
        ax.set_xlabel("Year", fontsize=18)
        ax.set_ylabel(_axis_label(tracer_name, unit), fontsize=18)
        ax.tick_params(axis="both", labelsize=16)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))

    for ax in axs.flatten()[len(tracer_names):]:
        ax.remove()

    legend_items = legend_handles
    if not highlighted_any:
        legend_items = [handle for handle in legend_handles if handle.get_label() != highlight_label]

    fig.legend(
        legend_items,
        [handle.get_label() for handle in legend_items],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=min(len(legend_items), 3),
        fontsize=18,
        frameon=False,
    )
    if title:
        fig.suptitle(title, fontsize=15, y=1.08)
        fig.tight_layout(rect=(0, 0, 1, 0.90))
    else:
        fig.tight_layout(rect=(0, 0, 1, 0.94))
    return _save_figure(fig, filename)


def plot_objective_summary(
    objective_frame: pd.DataFrame,
    posterior_results: dict[str, object],
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "Reference parameters",
    filename: str | Path | None = None,
    title: str = "Objective landscape and estimated parameters",
):
    """
    Plot pairwise parameter views colored by objective value.
    """
    apply_example_style()
    if not param_names:
        raise ValueError("At least one parameter is required.")
    objective_col = "log-ojf" if "log-ojf" in objective_frame.columns else "obj_function"
    if objective_col not in objective_frame.columns:
        raise ValueError("Objective frame must contain 'log-ojf' or 'obj_function'.")

    if len(param_names) == 1:
        pairs = [(param_names[0], objective_col)]
    else:
        pairs = list(combinations(param_names, 2))
    pairs = pairs[:3]

    ncols = len(pairs)
    fig_width = 5.6 * ncols + 1.4
    fig, axs = plt.subplots(1, ncols, figsize=(fig_width, 4.8), squeeze=False)
    axs = axs.flatten()

    grid_frame = objective_frame.copy()
    if len(grid_frame) > 8000:
        grid_frame = grid_frame.sample(8000, random_state=12345)
    best_grid = objective_frame.loc[pd.to_numeric(objective_frame[objective_col], errors="coerce").idxmin()]
    nearest_reference_row = _nearest_reference_objective_row(
        objective_frame,
        reference_params,
        param_names,
    )
    scalar = None

    for ax_index, ((xname, yname), ax) in enumerate(zip(pairs, axs)):
        if yname == objective_col:
            scalar = ax.scatter(
                grid_frame[xname],
                grid_frame[objective_col],
                c=grid_frame[objective_col],
                s=18,
                cmap=GRID_CMAP,
                alpha=0.55,
                edgecolors="none",
            )
            ax.scatter(
                best_grid[xname],
                best_grid[objective_col],
                marker="*",
                s=160,
                color="white",
                edgecolor=OBSERVED_COLOR,
                linewidth=0.9,
                label="Best prior grid point",
                zorder=4,
            )
            for method_index, (method_name, result) in enumerate(posterior_results.items()):
                frame = _ensure_frame(result)
                color = _method_color(method_name, method_index)
                sample = frame[[xname, "obj_function"]].dropna()
                ax.scatter(
                    sample[xname],
                    sample["obj_function"],
                    s=18,
                    color=color,
                    alpha=0.15,
                    label=f"{method_name} posterior samples" if ax_index == 0 else None,
                )
                best = _best_row(frame)
                if best is not None:
                    ax.scatter(
                        best[xname],
                        best["obj_function"],
                        marker="*",
                        s=130,
                        color=color,
                        edgecolor="white",
                        linewidth=0.8,
                        label=f"{method_name} posterior best" if ax_index == 0 else None,
                        zorder=5,
                    )
            if reference_params and xname in reference_params and nearest_reference_row is not None:
                ax.scatter(
                    float(reference_params[xname]),
                    float(nearest_reference_row[objective_col]),
                    marker="D",
                    s=90,
                    color=OBSERVED_COLOR,
                    edgecolor="white",
                    linewidth=0.8,
                    label=reference_label if ax_index == 0 else None,
                    zorder=6,
                )
            ax.set_xlabel(xname)
            ax.set_ylabel("Objective function")
        else:
            scalar = ax.scatter(
                grid_frame[xname],
                grid_frame[yname],
                c=grid_frame[objective_col],
                s=18,
                cmap=GRID_CMAP,
                alpha=0.55,
                edgecolors="none",
            )
            ax.scatter(
                best_grid[xname],
                best_grid[yname],
                marker="*",
                s=160,
                color="white",
                edgecolor=OBSERVED_COLOR,
                linewidth=0.9,
                label="Best prior grid point" if ax_index == 0 else None,
                zorder=4,
            )
            for method_index, (method_name, result) in enumerate(posterior_results.items()):
                frame = _ensure_frame(result)
                color = _method_color(method_name, method_index)
                sample = frame[[xname, yname]].dropna()
                ax.scatter(
                    sample[xname],
                    sample[yname],
                    s=20,
                    color=color,
                    alpha=0.15,
                    linewidths=0,
                    label=f"{method_name} posterior samples" if ax_index == 0 else None,
                )
                best = _best_row(frame)
                if best is not None:
                    ax.scatter(
                        best[xname],
                        best[yname],
                        marker="*",
                        s=130,
                        color=color,
                        edgecolor="white",
                        linewidth=0.8,
                        label=f"{method_name} posterior best" if ax_index == 0 else None,
                        zorder=5,
                    )
            if (
                reference_params
                and xname in reference_params
                and yname in reference_params
            ):
                ax.scatter(
                    float(reference_params[xname]),
                    float(reference_params[yname]),
                    marker="D",
                    s=90,
                    color=OBSERVED_COLOR,
                    edgecolor="white",
                    linewidth=0.8,
                    label=reference_label if ax_index == 0 else None,
                    zorder=6,
                )
            ax.set_xlabel(xname)
            ax.set_ylabel(yname)
        ax.set_title(f"{xname} vs {yname if yname != objective_col else 'objective'}")

    if scalar is not None:
        plot_right = 0.80 if ncols == 1 else 0.84
        colorbar_left = 0.88 if ncols == 1 else 0.90
        fig.subplots_adjust(left=0.10, right=plot_right, bottom=0.12, top=0.77, wspace=0.28)
        cax = fig.add_axes([colorbar_left, 0.18, 0.024, 0.56])
        cbar = fig.colorbar(scalar, cax=cax)
        cbar.set_label("Objective on prior grid (lower is better)")
    handles, labels = axs[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 3))
    fig.suptitle(title, fontsize=15, y=1.08)
    if scalar is None:
        fig.subplots_adjust(top=0.77, wspace=0.28)
    return _save_figure(fig, filename)


def plot_objective_solution_map(
    objective_frame: pd.DataFrame,
    posterior_frame: pd.DataFrame,
    param_names: list[str],
    reference_params: dict[str, float] | None = None,
    reference_label: str = "True parameters",
    filename: str | Path | None = None,
    title: str = "Expert view: posterior solutions colored by objective value",
):
    """
    Plot posterior solutions on top of the colored objective landscape.
    """
    apply_example_style()
    if not param_names:
        raise ValueError("At least one parameter is required.")

    objective_col = "log-ojf" if "log-ojf" in objective_frame.columns else "obj_function"
    posterior_objective_col = "obj_function" if "obj_function" in posterior_frame.columns else objective_col
    if objective_col not in objective_frame.columns:
        raise ValueError("Objective frame must contain 'log-ojf' or 'obj_function'.")
    if posterior_objective_col not in posterior_frame.columns:
        raise ValueError("Posterior frame must contain 'obj_function' or 'log-ojf'.")

    if len(param_names) == 1:
        pairs = [(param_names[0], objective_col)]
    else:
        pairs = list(combinations(param_names, 2))
    pairs = pairs[:3]

    ncols = len(pairs)
    fig_width = 5.8 * ncols + 1.6
    fig, axs = plt.subplots(1, ncols, figsize=(fig_width, 4.9), squeeze=False)
    axs = axs.flatten()

    grid_frame = objective_frame.copy()
    if len(grid_frame) > 9000:
        grid_frame = grid_frame.sample(9000, random_state=12345)
    post_frame = posterior_frame.copy()
    if len(post_frame) > 2500:
        post_frame = post_frame.sample(2500, random_state=12345)

    grid_values = pd.to_numeric(grid_frame[objective_col], errors="coerce")
    posterior_values = pd.to_numeric(post_frame[posterior_objective_col], errors="coerce")
    combined_values = pd.concat([grid_values.dropna(), posterior_values.dropna()], ignore_index=True)
    if combined_values.empty:
        raise ValueError("No valid objective values found for the expert objective plot.")

    vmin = float(combined_values.min())
    vmax = float(combined_values.max())
    best_posterior = _best_row(post_frame)
    nearest_reference_row = _nearest_reference_objective_row(
        objective_frame,
        reference_params,
        param_names,
    )

    # Updated color map
    new_cmap = "viridis"

    for xname, yname in pairs:
        ax = axs[pairs.index((xname, yname))]
        if yname == objective_col:
            scalar = ax.scatter(
                grid_frame[xname],
                grid_values,
                c=grid_values,
                s=18,
                cmap=new_cmap,  # Updated colormap
                vmin=vmin,
                vmax=vmax,
                alpha=0.24,
                edgecolors="none",
            )
            ax.scatter(
                post_frame[xname],
                posterior_values,
                c=posterior_values,
                s=34,
                cmap=new_cmap,  # Updated colormap
                vmin=vmin,
                vmax=vmax,
                alpha=0.78,
                edgecolors="none",  # Removed white borders
                linewidths=0.2,
                zorder=4,
            )
            if best_posterior is not None:
                ax.scatter(
                    best_posterior[xname],
                    best_posterior[posterior_objective_col],
                    marker="*",
                    s=140,
                    color="white",
                    edgecolor=OBSERVED_COLOR,
                    linewidth=0.9,
                    zorder=5,
                )
            if reference_params and xname in reference_params and nearest_reference_row is not None:
                ax.scatter(
                    float(reference_params[xname]),
                    float(nearest_reference_row[objective_col]),
                    marker="D",
                    s=90,
                    color=OBSERVED_COLOR,
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=6,
                )
            ax.set_ylabel("Objective function")
            ax.set_title(f"{xname} vs objective")
        else:
            scalar = _plot_interpolated_objective_surface(
                ax,
                grid_frame[xname],
                grid_frame[yname],
                grid_values,
                vmin=vmin,
                vmax=vmax,
            )
            ax.scatter(
                grid_frame[xname],
                grid_frame[yname],
                s=10,
                color="#d9e2e8",
                alpha=0.08,
                edgecolors="none",
                zorder=2,
            )
            ax.scatter(
                post_frame[xname],
                post_frame[yname],
                c=posterior_values,
                s=34,
                cmap=new_cmap,  # Updated colormap
                vmin=vmin,
                vmax=vmax,
                alpha=0.82,
                edgecolors="none",  # Removed white borders
                linewidths=0.2,
                zorder=4,
            )
            if best_posterior is not None:
                ax.scatter(
                    best_posterior[xname],
                    best_posterior[yname],
                    marker="*",
                    s=140,
                    color="white",
                    edgecolor=OBSERVED_COLOR,
                    linewidth=0.9,
                    zorder=5,
                )
            if reference_params and xname in reference_params and yname in reference_params:
                ax.scatter(
                    float(reference_params[xname]),
                    float(reference_params[yname]),
                    marker="D",
                    s=90,
                    color=OBSERVED_COLOR,
                    edgecolor="white",
                    linewidth=0.8,
                    zorder=6,
                )
            ax.set_ylabel(yname)
            ax.set_title(f"{xname} vs {yname}")
        ax.set_xlabel(xname)

    plot_right = 0.80 if ncols == 1 else 0.84
    colorbar_left = 0.88 if ncols == 1 else 0.90
    fig.subplots_adjust(left=0.10, right=plot_right, bottom=0.12, top=0.78, wspace=0.28)
    cax = fig.add_axes([colorbar_left, 0.18, 0.024, 0.58])
    cbar = fig.colorbar(scalar, cax=cax)
    cbar.set_label("Objective value (lower is better)")

    # Round values in the legend
    legend_handles = [
        Line2D([], [], marker="o", linestyle="", markersize=7, markerfacecolor="#808080", markeredgecolor="none", alpha=0.55, label="Interpolated prior objective surface"),
        Line2D([], [], marker="o", linestyle="", markersize=7, markerfacecolor="#2b8cbe", markeredgecolor="none", label="Posterior solutions colored by objective"),
        Line2D([], [], marker="*", linestyle="", markersize=12, markerfacecolor="white", markeredgecolor=OBSERVED_COLOR, label="Best posterior solution"),
    ]
    if reference_params:
        legend_handles.append(
            Line2D([], [], marker="D", linestyle="", markersize=8, markerfacecolor=OBSERVED_COLOR, markeredgecolor="white", label=reference_label)
        )
    fig.legend(
        legend_handles,
        [handle.get_label() for handle in legend_handles],
        loc="upper center",
        bbox_to_anchor=(0.48, 1.0),
        ncol=min(len(legend_handles), 3),
    )
    fig.suptitle(title, fontsize=15, y=1.08)
    return _save_figure(fig, filename)


def plot_temporal_fit_summary(
    craw,
    lpm_results,
    time_span_mode: str,
    lpm_number: int,
    filename: str | Path | None = None,
    title: str | None = None,
    start_year: float = 1960,
):
    """
    Plot median model response and uncertainty bands against observations.
    """
    apply_example_style()
    end_year = float(craw.cv["date"].max())
    tracers = convolution_tracers.ConvolutionTracers(
        names=craw.cv["element"].unique(),
        date=end_year,
    )
    lpm_list, _, _ = lpm_results.get_selection(
        lpm_number=lpm_number,
        time_span_mode=time_span_mode,
        array_resolution=1000,
    )
    if not lpm_list:
        raise ValueError("No calibrated LPMs available to build temporal fit figure.")

    predictions: dict[str, list[np.ndarray]] = {}
    prediction_dates: dict[str, np.ndarray] = {}
    for lpm in lpm_list:
        concentration_dict = tracers.convolve_date_range(lpm, start_year, end_year)
        for tracer_name, tracer_df in concentration_dict.items():
            ordered = tracer_df.sort_values("date")
            prediction_dates[tracer_name] = ordered["date"].to_numpy(dtype=float)
            predictions.setdefault(tracer_name, []).append(ordered["concentration"].to_numpy(dtype=float))

    tracer_names = list(dict.fromkeys(craw.cv["element"].tolist()))
    ncols = min(2, max(len(tracer_names), 1))
    nrows = ceil(max(len(tracer_names), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(6.3 * ncols, 4.0 * nrows), squeeze=False)

    legend_handles = []
    legend_labels = []

    for ax, tracer_name in zip(axs.flatten(), tracer_names):
        observed = craw.cv[craw.cv["element"] == tracer_name].sort_values("date")
        unit = observed["unit"].iloc[0] if "unit" in observed.columns and not observed.empty else None

        pred_array = np.vstack(predictions[tracer_name])
        pred_dates = prediction_dates[tracer_name]
        q10, q25, q50, q75, q90 = np.quantile(pred_array, [0.10, 0.25, 0.50, 0.75, 0.90], axis=0)

        band90 = ax.fill_between(pred_dates, q10, q90, color=INTERVAL_90_COLOR, alpha=0.8)
        band50 = ax.fill_between(pred_dates, q25, q75, color=INTERVAL_50_COLOR, alpha=0.75)
        median_line, = ax.plot(pred_dates, q50, color=MEDIAN_COLOR, linewidth=2.2)

        has_error = "error" in observed.columns and np.any(pd.to_numeric(observed["error"], errors="coerce") > 0)
        error = observed["error"] if has_error else None
        obs = ax.errorbar(
            observed["date"],
            observed["concentration"],
            yerr=error,
            fmt="o",
            color=OBSERVED_COLOR,
            ecolor="#4d4d4d",
            elinewidth=1.1,
            capsize=2,
            ms=5,
        )

        ax.set_title(_pretty_tracer_name(tracer_name))
        ax.set_xlabel("Year")
        ax.set_ylabel(_axis_label(tracer_name, unit))

        if not legend_handles:
            legend_handles = [obs, median_line, band50, band90]
            legend_labels = ["Observations", "Median model", "50% interval", "90% interval"]

    for ax in axs.flatten()[len(tracer_names):]:
        ax.remove()

    if legend_handles:
        fig.legend(legend_handles, legend_labels, loc="upper center", ncol=4)
        fig.subplots_adjust(top=0.82)
    fig.suptitle(title or "Temporal fit summary", fontsize=15, y=1.02)
    fig.tight_layout()
    return _save_figure(fig, filename)
