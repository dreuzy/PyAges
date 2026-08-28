# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Case partitioning and stable directory labels for temporal workflows."""

from __future__ import annotations

import pandas as pd

from pyages.concentrations import Concentrations


def format_date_label(date_value: float) -> str:
    """Return a lossless decimal-year label suitable for a directory name."""
    label = repr(float(date_value))
    if label.endswith(".0"):
        label = label[:-2]
    return label.replace(".", "_")


def build_case_frames(
    observations: Concentrations,
    mode: str,
) -> list[tuple[str, pd.DataFrame]]:
    """Partition observations into the cases required by a temporal mode."""
    if mode == "span":
        return [("span_full", observations.frame)]
    cases = [
        (
            f"date_{format_date_label(date)}",
            observations.frame[observations.frame["date"] == date],
        )
        for date in sorted(observations.frame["date"].unique())
    ]
    labels = [label for label, _frame in cases]
    if len(labels) != len(set(labels)):
        raise ValueError("Distinct observation dates produce colliding case labels")
    return cases


__all__ = ["build_case_frames", "format_date_label"]
