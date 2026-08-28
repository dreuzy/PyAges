# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Represent, normalize, and merge tracer concentration series.

The normalized in-memory representation maps each tracer name to a defensive,
date-sorted DataFrame. Replicate tracer/date observations remain valid in that
long representation. Wide tables have no replicate key, so their merge
boundary requires unique dates and rejects column-name collisions explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from pyages.concentrations._container import Concentrations
from pyages.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

ConcentrationSeries = dict[str, pd.DataFrame]


def _normalized_series_frame(frame: pd.DataFrame, *, tracer: str) -> pd.DataFrame:
    """Validate and copy one tracer time series."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"Concentration series {tracer!r} must be a pandas DataFrame")
    if frame.columns.duplicated().any():
        raise ValueError(f"Concentration series {tracer!r} has duplicate columns")
    required = {DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Concentration series {tracer!r} is missing columns: " + ", ".join(missing)
        )
    if frame.empty:
        raise ValueError(f"Concentration series {tracer!r} must not be empty")

    normalized = frame.loc[
        :, [DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN]
    ].copy()
    for column in (DATE_COLUMN, CONCENTRATION_COLUMN):
        try:
            normalized[column] = pd.to_numeric(normalized[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Concentration series {tracer!r} column {column!r} must be numeric"
            ) from exc
        values = normalized[column].to_numpy(dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError(
                f"Concentration series {tracer!r} column {column!r} must be finite"
            )

    if normalized[ELEMENT_COLUMN].isna().any():
        raise ValueError(
            f"Concentration series {tracer!r} elements must not be missing"
        )
    normalized[ELEMENT_COLUMN] = normalized[ELEMENT_COLUMN].map(str)
    elements = normalized[ELEMENT_COLUMN].unique().tolist()
    if elements != [tracer]:
        raise ValueError(
            f"Concentration series key {tracer!r} does not match element values "
            f"{elements!r}"
        )
    return normalized.sort_values(DATE_COLUMN).reset_index(drop=True)


def _validate_tracer_name(tracer: object, *, context: str) -> str:
    """Return a non-empty, already stripped tracer name."""
    if not isinstance(tracer, str) or not tracer or tracer != tracer.strip():
        raise ValueError(f"{context} must be non-empty, stripped strings")
    return tracer


def _normalize_mapping(
    concentrations: Mapping[str, pd.DataFrame],
) -> ConcentrationSeries:
    """Normalize an existing tracer-to-frame mapping."""
    if not concentrations:
        raise ValueError("Concentration series must contain at least one tracer")
    normalized: ConcentrationSeries = {}
    for raw_tracer, frame in concentrations.items():
        tracer = _validate_tracer_name(
            raw_tracer,
            context="Concentration series keys",
        )
        normalized[tracer] = _normalized_series_frame(frame, tracer=tracer)
    return normalized


def _normalize_long_frame(concentrations: pd.DataFrame) -> ConcentrationSeries:
    """Split and normalize a long-form concentration frame by tracer."""
    if concentrations.columns.duplicated().any():
        raise ValueError("Concentration series DataFrame has duplicate columns")
    required = {DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN}
    if not required.issubset(concentrations.columns):
        raise ValueError(
            "DataFrame must contain columns 'date', 'concentration', 'element'."
        )
    if concentrations.empty:
        raise ValueError("Concentration series must contain at least one row")
    if concentrations[ELEMENT_COLUMN].isna().any():
        raise ValueError("Concentration elements must not be missing")

    series_by_tracer: ConcentrationSeries = {}
    for raw_tracer, group in concentrations.groupby(ELEMENT_COLUMN, sort=False):
        tracer = _validate_tracer_name(
            raw_tracer,
            context="Concentration elements",
        )
        series_by_tracer[tracer] = _normalized_series_frame(group, tracer=tracer)
    return series_by_tracer


def normalize_series(
    concentrations: pd.DataFrame | Mapping[str, pd.DataFrame],
) -> ConcentrationSeries:
    """Return defensive, date-sorted tracer series in canonical long form."""
    if isinstance(concentrations, Mapping):
        return _normalize_mapping(concentrations)
    if isinstance(concentrations, pd.DataFrame):
        return _normalize_long_frame(concentrations)
    raise TypeError(
        "Unsupported 'concentrations' format (expected dict or DataFrame with 'element')."
    )


def merge_model_into_table(
    merged: pd.DataFrame | None,
    series_by_tracer: Mapping[str, pd.DataFrame],
    model_id: int,
) -> pd.DataFrame:
    """
    Merge one model's concentrations into a wide table.

    Parameters
    ----------
    merged : DataFrame or None
        Existing merged table, or None to initialize.
    series_by_tracer : dict
        Dict of tracer -> DataFrame(date, concentration, element).
    model_id : int
        Identifier suffix for column names (e.g., cfc11_3).

    Returns
    -------
    DataFrame
        A new date-sorted wide table. The input table is not modified.

    Raises
    ------
    ValueError
        If dates or generated output column names are not unique.
    """
    if isinstance(model_id, bool) or not isinstance(model_id, int) or model_id < 1:
        raise ValueError("model_id must be a positive integer")

    series = normalize_series(series_by_tracer)
    if not series:
        raise ValueError("series_by_tracer must contain at least one tracer series")

    if merged is None:
        result = pd.DataFrame(columns=[DATE_COLUMN])
    else:
        if not isinstance(merged, pd.DataFrame):
            raise TypeError("merged must be a pandas DataFrame or None")
        if DATE_COLUMN not in merged.columns:
            raise ValueError("merged table must contain a 'date' column")
        if merged[DATE_COLUMN].duplicated().any():
            raise ValueError("merged table must contain unique dates")
        result = merged.copy()

    for tracer, frame in series.items():
        if frame[DATE_COLUMN].duplicated().any():
            raise ValueError(
                f"Concentration series {tracer!r} contains duplicate dates; "
                "wide-table merges require one value per tracer and date"
            )
        output_column = f"{tracer}_{model_id}"
        if output_column in result.columns:
            raise ValueError(f"Concentration column already exists: {output_column}")
        temp = frame[[DATE_COLUMN, CONCENTRATION_COLUMN]].rename(
            columns={CONCENTRATION_COLUMN: output_column}
        )
        result = pd.merge(
            result,
            temp,
            on=DATE_COLUMN,
            how="outer",
            sort=True,
            validate="one_to_one",
        )

    return result.sort_values(DATE_COLUMN).reset_index(drop=True)


class ConcentrationChronicle:
    """Concentration series grouped by tracer across time.

    Exactly one input representation is required. ``observations`` retains the
    validated long-form source when available; ``series`` always contains
    defensive, date-sorted tracer tables.
    """

    def __init__(
        self,
        observations: Concentrations | None = None,
        series: Mapping[str, pd.DataFrame] | pd.DataFrame | None = None,
    ) -> None:
        """Build a chronicle from observations or prepared tracer series."""
        if (observations is None) == (series is None):
            raise ValueError("Provide exactly one of observations or series")
        if observations is not None and not isinstance(observations, Concentrations):
            raise TypeError("observations must be a Concentrations instance")

        self.observations = observations
        source = observations.frame if observations is not None else series
        self.series = normalize_series(source)

    def plot(
        self,
        fig: Figure,
        axs: Axes | Sequence[Axes],
        graph_type: Literal["scatter", "line"] = "scatter",
    ) -> None:
        """Plot all tracer series on caller-owned axes."""
        from pyages.concentrations.plotting import plot_tracer_series

        plot_tracer_series(self.series, axs, graph_type=graph_type)
        fig.suptitle("Tracer", fontsize=16, y=1.02)

    def rebuild(self) -> None:
        """Rebuild tracer tables from the retained observations."""
        if self.observations is None:
            raise RuntimeError(
                "rebuild() requires a chronicle created from observations"
            )
        self.series = normalize_series(self.observations.frame)

    def save(self, filename: str | Path) -> None:
        """Save the chronicle as a single wide TSV table."""
        from pyages.data_io.concentrations import save_tracer_series_table

        save_tracer_series_table(self.series, filename)


__all__ = [
    "ConcentrationChronicle",
    "ConcentrationSeries",
    "merge_model_into_table",
    "normalize_series",
]
