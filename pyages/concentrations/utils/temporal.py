# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Shared computation of temporal posterior prediction summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class TemporalPredictionSummary:
    """Five posterior quantiles evaluated on one tracer date grid."""

    dates: np.ndarray
    q10: np.ndarray
    q25: np.ndarray
    median: np.ndarray
    q75: np.ndarray
    q90: np.ndarray


def _validate_tracer_set(
    tracer_names: set[str],
    expected_tracers: set[str] | None,
    realization_index: int,
) -> set[str]:
    """Return the initial tracer set or validate a subsequent realization."""
    if expected_tracers is None:
        if not tracer_names:
            raise ValueError("Temporal convolution returned no tracer series")
        return tracer_names
    if tracer_names != expected_tracers:
        missing = sorted(expected_tracers - tracer_names)
        extra = sorted(tracer_names - expected_tracers)
        raise ValueError(
            "Temporal convolution returned inconsistent tracer sets for "
            f"realization {realization_index}: missing={missing}, extra={extra}"
        )
    return expected_tracers


def _prediction_arrays(
    tracer_name: str, tracer_frame: Any
) -> tuple[np.ndarray, np.ndarray]:
    """Validate and normalize one temporal prediction series."""
    required = {"date", "concentration"}
    missing_columns = sorted(required.difference(tracer_frame.columns))
    if missing_columns:
        raise ValueError(
            f"Temporal predictions for {tracer_name!r} are missing columns: "
            + ", ".join(missing_columns)
        )
    ordered = tracer_frame.sort_values("date")
    dates = ordered["date"].to_numpy(dtype=float)
    values = ordered["concentration"].to_numpy(dtype=float)
    if dates.size == 0:
        raise ValueError(f"Temporal predictions for {tracer_name!r} must not be empty")
    if not np.all(np.isfinite(dates)) or not np.all(np.isfinite(values)):
        raise ValueError(f"Temporal predictions for {tracer_name!r} must be finite")
    if np.unique(dates).size != dates.size:
        raise ValueError(
            f"Temporal predictions for {tracer_name!r} contain duplicate dates"
        )
    return dates, values


def _validate_date_grid(
    tracer_name: str,
    previous_dates: np.ndarray | None,
    dates: np.ndarray,
) -> None:
    """Reject model realizations evaluated on different grids."""
    if previous_dates is not None and (
        previous_dates.shape != dates.shape
        or not np.allclose(previous_dates, dates, rtol=0.0, atol=1e-10)
    ):
        raise ValueError(
            f"Model realizations use inconsistent date grids for {tracer_name!r}"
        )


def summarize_temporal_predictions(
    tracers: Any,
    lpm_list: Sequence[Any],
    start_year: float,
    end_year: float,
) -> dict[str, TemporalPredictionSummary]:
    """Convolve LPM realizations and compute consistent posterior quantiles.

    Every realization must produce the same tracers on the same date grids.
    Checking that contract here prevents plotting functions from silently
    combining misaligned model values.
    """
    if not lpm_list:
        raise ValueError("At least one calibrated LPM is required")

    values_by_tracer: dict[str, list[np.ndarray]] = {}
    dates_by_tracer: dict[str, np.ndarray] = {}
    expected_tracers: set[str] | None = None

    for realization_index, lpm in enumerate(lpm_list):
        realization = tracers.convolve_date_range(lpm, start_year, end_year)
        tracer_names = set(realization)
        expected_tracers = _validate_tracer_set(
            tracer_names,
            expected_tracers,
            realization_index,
        )

        for tracer_name, tracer_frame in realization.items():
            dates, values = _prediction_arrays(tracer_name, tracer_frame)
            _validate_date_grid(
                tracer_name,
                dates_by_tracer.get(tracer_name),
                dates,
            )
            dates_by_tracer[tracer_name] = dates
            values_by_tracer.setdefault(tracer_name, []).append(values)

    summaries = {}
    for tracer_name, realizations in values_by_tracer.items():
        q10, q25, median, q75, q90 = np.quantile(
            np.vstack(realizations),
            [0.10, 0.25, 0.50, 0.75, 0.90],
            axis=0,
        )
        summaries[tracer_name] = TemporalPredictionSummary(
            dates=dates_by_tracer[tracer_name],
            q10=q10,
            q25=q25,
            median=median,
            q75=q75,
            q90=q90,
        )
    return summaries


__all__ = ["TemporalPredictionSummary", "summarize_temporal_predictions"]
