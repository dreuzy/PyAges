# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Serialize prepared concentration tables with consistent TSV formatting.

Scientific normalization remains in :mod:`pyages.concentrations.series`;
this module owns only directory creation, wide-table assembly, and filesystem
serialization.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from pyages.concentrations.schema import DATE_COLUMN
from pyages.concentrations.series import normalize_series


def save_concentrations_table(table: pd.DataFrame, filepath: str | Path) -> None:
    """
    Save a wide concentration table to disk as TSV.

    Parameters
    ----------
    table : DataFrame
        Table with 'date' column and tracer/model columns.
    filepath : str or Path
        Output file path.
    """
    if not isinstance(table, pd.DataFrame):
        raise TypeError("table must be a pandas DataFrame")
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, sep="\t", index=False, encoding="utf-8")


def save_tracer_series_table(
    series_by_tracer: Mapping[str, pd.DataFrame], filepath: str | Path
) -> None:
    """
    Save tracer series as a single wide table.

    Parameters
    ----------
    series_by_tracer : dict
        Dict {tracer: DataFrame(date, concentration, element)}.
    filepath : str or Path
        Output file path.
    """
    series = normalize_series(series_by_tracer)
    merged: pd.DataFrame | None = None
    for tracer, df in series.items():
        if df[DATE_COLUMN].duplicated().any():
            raise ValueError(
                f"Concentration series {tracer!r} contains duplicate dates; "
                "wide-table export requires one value per tracer and date"
            )
        temp = df[[DATE_COLUMN, "concentration"]].rename(
            columns={"concentration": tracer}
        )
        if merged is None:
            merged = temp
        else:
            merged = pd.merge(
                merged,
                temp,
                on=DATE_COLUMN,
                how="outer",
                sort=True,
                validate="one_to_one",
            )
    if merged is None:
        merged = pd.DataFrame(columns=[DATE_COLUMN])
    else:
        merged = merged.sort_values(DATE_COLUMN).reset_index(drop=True)
    save_concentrations_table(merged, filepath)


def save_distributions_tables(
    pdf: pd.DataFrame,
    stats: pd.DataFrame,
    output_dir: str | Path,
    pdf_name: str = "distributions.txt",
    stats_name: str = "distributions_stats.txt",
) -> None:
    """
    Save distributions (pdf) and summary stats tables as TSV files.

    Parameters
    ----------
    pdf : DataFrame
        Distribution samples (e.g., columns: t, p1, p2, ...).
    stats : DataFrame
        Summary statistics table for selected LPMs.
    output_dir : str or Path
        Directory where files are written.
    pdf_name : str, optional
        Output filename for the PDF table.
    stats_name : str, optional
        Output filename for the statistics table.
    """
    if not isinstance(pdf, pd.DataFrame) or not isinstance(stats, pd.DataFrame):
        raise TypeError("pdf and stats must be pandas DataFrames")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(output_dir / pdf_name, sep="\t", index=False)
    stats.to_csv(output_dir / stats_name, sep="\t", index=False)


__all__ = [
    "save_concentrations_table",
    "save_distributions_tables",
    "save_tracer_series_table",
]
