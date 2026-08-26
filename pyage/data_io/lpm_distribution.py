"""Tabular output helpers for LPM sample distributions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_dist import LpmDist


def write_frame(frame: pd.DataFrame, target: str | Path, *, index: bool) -> None:
    """Write a dataframe as TSV after creating its parent directory."""
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=index)


def write_distribution(distribution: "LpmDist", target: str | Path) -> None:
    """Write all stored samples."""
    write_frame(distribution.frame, target, index=True)


def write_histograms(distribution: "LpmDist", target: str | Path) -> None:
    """Write one histogram table per model parameter."""
    base_path = Path(target)
    for name, payload in distribution.histograms().items():
        output = base_path.with_name(f"{base_path.stem}_{name}{base_path.suffix}")
        values, histogram = _histogram_values(payload)
        frame = pd.DataFrame({"val": values, "hist": histogram})
        write_frame(frame, output, index=False)


def _histogram_values(payload: dict[str, Any]) -> tuple[Any, Any]:
    """Return aligned bin starts and histogram values from a payload."""
    return payload["bins"][:-1], payload["hist"]


def write_statistics(distribution: "LpmDist", target: str | Path) -> None:
    """Write descriptive statistics for all numeric sample columns."""
    write_frame(distribution.statistics(), target, index=True)
