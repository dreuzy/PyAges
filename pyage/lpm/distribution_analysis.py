"""Pure analysis helpers for posterior LPM sample tables."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd

from pyage.config.runtime import subdivide_interval


def select_models(
    template: Any,
    frame: pd.DataFrame,
    count: int,
    resolution: int,
) -> tuple[list[Any], pd.DataFrame, pd.DataFrame]:
    """Select reproducible model realizations and compute their PDFs/moments."""
    if count < 0:
        raise ValueError("count must be non-negative")
    if resolution < 2:
        raise ValueError("resolution must be at least 2")

    time = subdivide_interval(0, 70, resolution - 1)
    pdf_values = np.empty((count + 1, resolution))
    pdf_values[0] = time
    pdf_names = ["t"]
    statistics = pd.DataFrame(index=range(count), columns=template.moments_name())
    selected = []
    rng = np.random.default_rng(12345)
    for position in range(count):
        lines = template.load_sample(frame, selection="random_line", rng=rng)
        if lines is None:
            pdf_values[position + 1] = np.nan
            pdf_names.append("p")
            continue
        selected.append(copy.deepcopy(template))
        pdf_values[position + 1] = template.pdf(time)
        pdf_names.append(f"p{lines}")
        statistics.iloc[position] = template.moments()

    pdf = pd.DataFrame(pdf_values.T, columns=pdf_names)
    return selected, pdf, statistics


def add_moment_columns(template: Any, frame: pd.DataFrame) -> pd.DataFrame:
    """Return a sample table enriched with one column per LPM moment."""
    moment_names = template.moments_name()
    moment_values = []
    for position in range(len(frame)):
        lines = template.load_sample(frame, selection="line", row=position)
        moment_values.append(
            template.moments() if lines is not None else [np.nan] * len(moment_names)
        )

    base = frame.drop(columns=moment_names, errors="ignore").reset_index(drop=True)
    moments = pd.DataFrame(moment_values, columns=moment_names)
    return pd.concat([base, moments], axis=1)


def compute_histograms(
    template: Any, frame: pd.DataFrame, bin_count: int
) -> dict[str, dict[str, np.ndarray]]:
    """Compute density histograms for every model parameter."""
    if bin_count < 1:
        raise ValueError("bin_count must be positive")
    histograms = {}
    for name in template.p:
        histogram, bins = np.histogram(frame[name], bins=bin_count, density=True)
        histograms[name] = {"hist": histogram, "bins": bins}
    return histograms


def append_target_statistics(template: Any, frame: pd.DataFrame, data: dict) -> None:
    """Append descriptive and target-relative statistics to ``data`` in place."""
    statistics = frame.describe()
    for name in template.p:
        target = template.p[name]
        data[f"{name}_target"] = [target]
        data[f"{name}_difference"] = [statistics.loc["mean", name] - target]
        data[f"{name}_rate_mean"] = [statistics.loc["mean", name] / target]
        data[f"{name}_rate_std"] = [statistics.loc["std", name] / target]
    for column in statistics.columns:
        for statistic in statistics.index:
            data[f"{column}_{statistic}"] = [statistics.loc[statistic, column]]
