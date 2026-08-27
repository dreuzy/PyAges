# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Pure analysis helpers for LPM sample tables."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd

from pyages.config.runtime import subdivide_interval


def select_model_realizations(
    template: Any,
    frame: pd.DataFrame,
    count: int,
    resolution: int,
    rng: np.random.Generator | None = None,
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
    if rng is None:
        rng = np.random.default_rng(12345)
    for position in range(count):
        model = copy.deepcopy(template)
        selected_row = model.load_sample(frame, selection="random_line", rng=rng)
        if selected_row is None:
            pdf_values[position + 1] = np.nan
            pdf_names.append("p")
            continue
        selected.append(model)
        pdf_values[position + 1] = model.pdf(time)
        pdf_names.append(f"p{selected_row}")
        statistics.iloc[position] = model.moments()

    pdf = pd.DataFrame(pdf_values.T, columns=pdf_names)
    return selected, pdf, statistics


def add_moment_columns(template: Any, frame: pd.DataFrame) -> pd.DataFrame:
    """Return a sample table enriched with one column per LPM moment."""
    moment_names = template.moments_name()
    moment_values = []
    model = copy.deepcopy(template)
    for position in range(len(frame)):
        model.load_sample(frame, selection="line", row=position)
        moment_values.append(model.moments())

    base = frame.drop(columns=moment_names, errors="ignore").reset_index(drop=True)
    moments = pd.DataFrame(moment_values, columns=moment_names)
    return pd.concat([base, moments], axis=1)


def compute_parameter_histograms(
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


def append_reference_statistics(template: Any, frame: pd.DataFrame, data: dict) -> None:
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


__all__ = [
    "add_moment_columns",
    "append_reference_statistics",
    "compute_parameter_histograms",
    "select_model_realizations",
]
