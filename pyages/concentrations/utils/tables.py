# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Table helpers for concentration time series.

Purpose
-------
Normalize concentration data structures and assemble wide tables used for
model comparisons and exports.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from pyages.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
)

ConcentrationSeries = dict[str, pd.DataFrame]


def _normalized_series_frame(frame: pd.DataFrame, *, tracer: str) -> pd.DataFrame:
    """Validate and copy one tracer time series."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"Concentration series {tracer!r} must be a pandas DataFrame")
    required = {DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Concentration series {tracer!r} is missing columns: " + ", ".join(missing)
        )
    if frame.columns.duplicated().any():
        raise ValueError(f"Concentration series {tracer!r} has duplicate columns")

    normalized = frame.loc[
        :, [DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN]
    ].copy()
    elements = normalized[ELEMENT_COLUMN].dropna().astype(str).unique().tolist()
    if elements and elements != [tracer]:
        raise ValueError(
            f"Concentration series key {tracer!r} does not match element values "
            f"{elements!r}"
        )
    return normalized.sort_values(DATE_COLUMN).reset_index(drop=True)


def normalize_series(
    concentrations: pd.DataFrame | Mapping[str, pd.DataFrame],
) -> ConcentrationSeries:
    """
    Normalize concentrations to a dict {tracer: DataFrame(date, concentration, element)}.

    Parameters
    ----------
    concentrations : DataFrame or dict
        Either a dict already keyed by tracer, or a long-form DataFrame
        with columns ["date", "concentration", "element"].

    Returns
    -------
    dict[str, DataFrame]
        Defensive, date-sorted copies containing only the three canonical
        chronicle columns.
    """
    if isinstance(concentrations, Mapping):
        normalized: ConcentrationSeries = {}
        for tracer, frame in concentrations.items():
            if not isinstance(tracer, str) or not tracer.strip():
                raise ValueError("Concentration series keys must be non-empty strings")
            normalized[tracer] = _normalized_series_frame(frame, tracer=tracer)
        return normalized
    if isinstance(concentrations, pd.DataFrame):
        required = {DATE_COLUMN, CONCENTRATION_COLUMN, ELEMENT_COLUMN}
        if not required.issubset(concentrations.columns):
            raise ValueError(
                "DataFrame must contain columns 'date', 'concentration', 'element'."
            )
        if concentrations[ELEMENT_COLUMN].isna().any():
            raise ValueError("Concentration elements must not be missing")
        cv: ConcentrationSeries = {}
        for tracer, group in concentrations.groupby(ELEMENT_COLUMN, sort=False):
            if not isinstance(tracer, str) or not tracer.strip():
                raise ValueError("Concentration elements must be non-empty strings")
            cv[tracer] = _normalized_series_frame(group, tracer=tracer)
        return cv
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
