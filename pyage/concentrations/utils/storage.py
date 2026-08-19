# -*- coding: utf-8 -*-
"""
File output helpers for concentration tables.

Purpose
-------
Save prepared concentration tables to disk with consistent formatting.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


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
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, sep="\t", index=False, encoding="utf-8")


def save_tracer_series_table(cv: dict[str, pd.DataFrame], filepath: str | Path) -> None:
    """
    Save tracer series as a single wide table.

    Parameters
    ----------
    cv : dict
        Dict {tracer: DataFrame(date, concentration, element)}.
    filepath : str or Path
        Output file path.
    """
    merged = None
    for tracer, df in cv.items():
        temp = df[["date", "concentration"]].rename(columns={"concentration": tracer})
        if merged is None:
            merged = temp
        else:
            merged = pd.merge(merged, temp, on="date", how="outer")
    if merged is None:
        merged = pd.DataFrame(columns=["date"])
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
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf.to_csv(output_dir / pdf_name, sep="\t", index=False)
    stats.to_csv(output_dir / stats_name, sep="\t", index=False)
