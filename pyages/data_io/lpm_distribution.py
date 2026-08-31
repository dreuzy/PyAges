# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tabular output helpers for LPM sample distributions."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from pyages.lpm.samples.table import LpmSampleTable


def read_frame(source: str | Path, *, index: bool) -> pd.DataFrame:
    """Read one UTF-8 TSV written by :func:`write_frame`.

    Parameters
    ----------
    source : str or pathlib.Path
        Existing tab-separated file.
    index : bool
        Whether the first serialized column is the dataframe index.
    """
    return pd.read_csv(
        Path(source),
        sep="\t",
        encoding="utf-8",
        index_col=0 if index else None,
    )


def write_frame(frame: pd.DataFrame, target: str | Path, *, index: bool) -> None:
    """Atomically write a dataframe as UTF-8 TSV."""
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=".pyages-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            frame.to_csv(stream, sep="\t", index=index)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def write_distribution(distribution: "LpmSampleTable", target: str | Path) -> None:
    """Validate and atomically write all stored samples."""
    distribution.validate()
    write_frame(distribution.frame, target, index=True)


def read_distribution(source: str | Path) -> pd.DataFrame:
    """Read a calibrated LPM sample table and restore its serialized index."""
    return read_frame(source, index=True)


def _histogram_path(target: str | Path, parameter_name: str) -> Path:
    """Return the per-parameter path used by histogram readers and writers."""
    base_path = Path(target)
    return base_path.with_name(f"{base_path.stem}_{parameter_name}{base_path.suffix}")


def write_histograms(distribution: "LpmSampleTable", target: str | Path) -> None:
    """Validate samples and write one histogram table per model parameter."""
    distribution.validate()
    for name, payload in distribution.histograms().items():
        values, histogram = _histogram_values(payload)
        frame = pd.DataFrame({"val": values, "hist": histogram})
        write_frame(frame, _histogram_path(target, name), index=False)


def read_histogram(source: str | Path, parameter_name: str) -> pd.DataFrame:
    """Read one parameter histogram from an existing histogram file family."""
    frame = read_frame(_histogram_path(source, parameter_name), index=False)
    expected_columns = ["val", "hist"]
    if list(frame.columns) != expected_columns:
        raise ValueError(
            f"Invalid histogram columns for {parameter_name!r}: "
            f"expected {expected_columns}, got {list(frame.columns)}"
        )
    return frame


def read_histograms(
    source: str | Path,
    parameter_names: Iterable[str],
) -> dict[str, pd.DataFrame]:
    """Read one histogram table for every requested model parameter."""
    return {name: read_histogram(source, name) for name in parameter_names}


def _histogram_values(payload: dict[str, Any]) -> tuple[Any, Any]:
    """Return aligned bin starts and histogram values from a payload."""
    return payload["bins"][:-1], payload["hist"]


def write_statistics(distribution: "LpmSampleTable", target: str | Path) -> None:
    """Validate samples and atomically write their descriptive statistics."""
    distribution.validate()
    write_frame(distribution.statistics(), target, index=True)


def read_statistics(source: str | Path) -> pd.DataFrame:
    """Read an LPM descriptive-statistics table and restore its row index."""
    return read_frame(source, index=True)
