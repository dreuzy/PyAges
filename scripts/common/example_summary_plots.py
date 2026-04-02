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
INTERVAL_50_COLOR = "#6baed6"
INTERVAL_90_COLOR = "#c6dbef"
GRID_CMAP = "cividis_r"


def apply_example_style() -> None:
    """Apply a lighter plotting style for didactic example figures."""
    plt.rcParams.update(
        {
            "figure.figsize": (7.0, 4.5),
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "axes.titleweight": "semibold",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linestyle": "--",
            "legend.fontsize": 9,
            "legend.frameon": False,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
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
):
    """
    Plot observation-only panels for each tracer.
    """
    apply_example_style()
    df = cdata.cv.copy()
    tracers = list(dict.fromkeys(df["element"].tolist()))
    ncols = min(3, max(len(tracers), 1))
    nrows = ceil(max(len(tracers), 1) / ncols)
    fig, axs = plt.subplots(nrows, ncols, figsize=(6.2 * ncols, 3.8 * nrows), squeeze=False)

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
        unit = tracer_df["unit"].iloc[0] if "unit" in tracer_df.columns and not tracer_df.empty else None
        ax.set_title(_pretty_tracer_name(tracer))
        ax.set_xlabel("Year")
        ax.set_ylabel(_axis_label(tracer, unit))

    for ax in axs.flatten()[len(tracers):]:
        ax.remove()

    fig.suptitle(title, fontsize=15, y=1.04)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
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

    fig, axs = plt.subplots(1, len(pairs), figsize=(5.3 * len(pairs), 4.6), squeeze=False)
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
            label="Reachable space" if ax_index == 0 else None,
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
                alpha=0.65,
                color=color,
                linewidths=0,
                label=f"{method_name} samples" if ax_index == 0 else None,
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
                    label=f"{method_name} best" if ax_index == 0 else None,
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

    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 4))
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
                label=method_name,
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
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 4))
    fig.suptitle(title, fontsize=15, y=1.06)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
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
    fig, axs = plt.subplots(1, ncols, figsize=(5.4 * ncols, 4.6), squeeze=False)
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
                alpha=0.7,
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
                label="Best grid point",
                zorder=4,
            )
            for method_index, (method_name, result) in enumerate(posterior_results.items()):
                frame = _ensure_frame(result)
                color = _method_color(method_name, method_index)
                sample = frame[[xname, "obj_function"]].dropna()
                if len(sample) > 450:
                    sample = sample.sample(450, random_state=12345)
                ax.scatter(
                    sample[xname],
                    sample["obj_function"],
                    s=18,
                    color=color,
                    alpha=0.55,
                    label=f"{method_name} samples" if ax_index == 0 else None,
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
                        label=f"{method_name} best" if ax_index == 0 else None,
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
                alpha=0.72,
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
                label="Best grid point" if ax_index == 0 else None,
                zorder=4,
            )
            for method_index, (method_name, result) in enumerate(posterior_results.items()):
                frame = _ensure_frame(result)
                color = _method_color(method_name, method_index)
                sample = frame[[xname, yname]].dropna()
                if len(sample) > 450:
                    sample = sample.sample(450, random_state=12345)
                ax.scatter(
                    sample[xname],
                    sample[yname],
                    s=20,
                    color=color,
                    alpha=0.6,
                    linewidths=0,
                    label=f"{method_name} samples" if ax_index == 0 else None,
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
                        label=f"{method_name} best" if ax_index == 0 else None,
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
        fig.colorbar(scalar, ax=axs.tolist(), shrink=0.9, label="Lower is better")
    handles, labels = axs[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=min(len(labels), 4))
    fig.suptitle(title, fontsize=15, y=1.08)
    fig.subplots_adjust(top=0.77, wspace=0.28)
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
        concentration_dict = tracers.convolution_date_range(lpm, start_year, end_year)
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
