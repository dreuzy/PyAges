# -*- coding: utf-8 -*-
"""
Table helpers for concentration time series.

Purpose
-------
Normalize concentration data structures and assemble wide tables used for
model comparisons and exports.
"""

from typing import Dict, Optional

import pandas as pd


def to_cv_dict(concentrations: pd.DataFrame | Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Normalize concentrations to a dict {tracer: DataFrame(date, concentration, element)}.

    Parameters
    ----------
    concentrations : DataFrame or dict
        Either a dict already keyed by tracer, or a long-form DataFrame
        with columns ["date", "concentration", "element"].
    """
    if isinstance(concentrations, dict):
        return concentrations
    if isinstance(concentrations, pd.DataFrame):
        if not {"date", "concentration", "element"}.issubset(concentrations.columns):
            raise ValueError(
                "DataFrame must contain columns 'date', 'concentration', 'element'."
            )
        cv: Dict[str, pd.DataFrame] = {}
        for tracer, group in concentrations.groupby("element"):
            cv[tracer] = group[["date", "concentration", "element"]].reset_index(drop=True)
        return cv
    raise TypeError(
        "Unsupported 'concentrations' format (expected dict or DataFrame with 'element')."
    )


def merge_model_into_table(
    merged: Optional[pd.DataFrame],
    cv_dict: Dict[str, pd.DataFrame],
    model_id: int,
) -> pd.DataFrame:
    """
    Merge one model's concentrations into a wide table.

    Parameters
    ----------
    merged : DataFrame or None
        Existing merged table, or None to initialize.
    cv_dict : dict
        Dict of tracer -> DataFrame(date, concentration, element).
    model_id : int
        Identifier suffix for column names (e.g., cfc11_3).
    """
    if merged is None:
        first_df = next(iter(cv_dict.values()))
        merged = (
            first_df[["date"]]
            .drop_duplicates()
            .sort_values("date")
            .reset_index(drop=True)
        )

    for tracer, df in cv_dict.items():
        temp = df[["date", "concentration"]].rename(
            columns={"concentration": f"{tracer}_{model_id}"}
        )
        merged = pd.merge(merged, temp, on="date", how="outer")

    return merged.sort_values("date").reset_index(drop=True)
