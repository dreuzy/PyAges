# -*- coding: utf-8 -*-
"""
Concentration data container and helpers.

Provides a lightweight wrapper around a pandas DataFrame to load, validate,
sample, and export tracer concentration data used by calibration workflows.

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pyage.concentrations.schema import (
    CONCENTRATION_COLUMN,
    ERROR_COLUMN,
    REFERENCE_COLUMNS,
)


def name_date(name: str, date: float) -> str:
    """Build a stable key from a tracer name and date."""
    return f"{name}-{date:.1f}".replace(".", "_")


class Concentrations:
    """
    Container for tracer concentrations and their metadata.

    The underlying data is stored in `cv` (a pandas DataFrame) with reference
    columns defined by `REFERENCE_COLUMNS` (e.g. element, concentration,
    error, unit, date).
    """

    def __init__(self, frame: pd.DataFrame) -> None:
        """Normalize and validate a copy of an observation dataframe."""
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("frame must be a pandas DataFrame")
        self.cv = frame.copy().reset_index(drop=True)
        self.__ensure_column(ERROR_COLUMN, 0.0)
        self.__ensure_column("unit", "mol/l")
        self.validate()

    @classmethod
    def from_file(cls, path: str | Path) -> "Concentrations":
        """Load observations from a tab-separated file."""
        return cls(pd.read_table(path, sep="\t", header=0))

    @classmethod
    def from_dataframe(cls, frame: pd.DataFrame) -> "Concentrations":
        """Build observations from an existing dataframe copy."""
        return cls(frame)

    def error_affect_from_mean(
        self, mean_value: np.ndarray, fraction: float = 0.01
    ) -> None:
        """
        Assign errors proportional to mean tracer concentrations.

        Args:
            mean_value: Mean value per tracer.
            fraction: Fraction of the mean value used as error.
        """
        mean_array = np.asarray(mean_value, dtype=float)
        missing_error = self.cv[ERROR_COLUMN].to_numpy(dtype=float) == 0.0
        self.cv.loc[missing_error, ERROR_COLUMN] = mean_array[missing_error] * fraction

    def error_affect_from_value(self, fraction: float) -> None:
        """
        Assign errors proportional to concentration values.

        Args:
            fraction: Fraction of the concentration used as error.
        """
        self.cv[ERROR_COLUMN] = fraction * self.cv[CONCENTRATION_COLUMN].to_numpy(
            dtype=float
        )

    def __ensure_column(self, name: str, default_value) -> None:
        """Ensure a column exists in cv; insert a default when missing."""
        if name not in self.cv.columns:
            self.cv[name] = default_value

    def validate(self) -> None:
        """Require the canonical columns and normalize their order."""
        missing = [column for column in REFERENCE_COLUMNS if column not in self.cv]
        if missing:
            raise ValueError(
                "Missing required columns in concentrations: " + ", ".join(missing)
            )
        self.cv = self.cv[list(REFERENCE_COLUMNS)]

    def sample_concentrations_with_errors(
        self, rng: np.random.Generator
    ) -> "Concentrations":
        """
        Samples concentrations from the distribution of errors given

        Args:
            rng: NumPy random number generator.

        Returns:
            Concentrations: Sampled concentrations using the error distribution.
        """
        sampled = self.from_dataframe(self.cv)
        draw = rng.standard_normal(size=len(sampled.cv))
        base = self.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        err = self.cv[ERROR_COLUMN].to_numpy(dtype=float)
        sampled.cv[CONCENTRATION_COLUMN] = base + err * draw
        return sampled

    def display(self, display_options) -> None:
        """Display the concentration table when text output is enabled."""
        if display_options.text:
            print(self.cv)

    def figure_concentrations(
        self,
        i1: int,
        i2: int,
        label_x: str | None = None,
        label_y: str | None = None,
    ) -> None:
        """Plot a scatter of two concentration values by row index."""
        if i1 >= len(self.cv) or i2 >= len(self.cv):
            raise IndexError("Index out of range for concentration plot.")
        plt.scatter(
            self.cv["concentration"][i1],
            self.cv["concentration"][i2],
            marker="o",
            c="r",
            s=150,
        )
        if label_x:
            plt.xlabel(label_x)
        if label_y:
            plt.ylabel(label_y)

    def names(self) -> list[str]:
        """Return tracer names as a list."""
        return [self.cv.iloc[i, 0] for i in range(len(self.cv.iloc[:, 0]))]

    def names_dates(self) -> list[str]:
        """Return tracer names combined with date and index."""
        return [
            self.cv.iloc[i, 0] + "_" + str(self.cv.loc[i]["date"]) + "_" + str(i)
            for i in range(len(self.cv.iloc[:, 0]))
        ]

    def cv_key_name_date(self) -> pd.DataFrame:
        """
        Return a copy with element keys expanded to element-date.

        Example:
            element  concentration  error  unit  date
            cfc11    0.0            1.0    pptv  1990

        Returns:
            DataFrame with element replaced by element-date keys.
        """
        cv = self.cv.copy()
        cv["element"] = [
            name_date(row["element"], row["date"]) for _, row in cv.iterrows()
        ]
        return cv
