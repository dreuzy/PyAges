# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Concentration data container and helpers.

Provides a lightweight wrapper around a pandas DataFrame to load, validate,
sample, and export tracer concentration data used by calibration workflows.

"""

from __future__ import annotations

from collections.abc import Iterable
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pyages.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
    ERROR_COLUMN,
    REFERENCE_COLUMNS,
    UNIT_COLUMN,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.collections import PathCollection

    from pyages.config.runtime import DisplayOptions


_DEFAULT_ERROR = 0.0
_DEFAULT_UNIT = "mol/l"


def name_date(name: str, date: float) -> str:
    """Build the historical one-decimal tracer/date key used by model tables."""
    return f"{name}-{date:.1f}".replace(".", "_")


class Concentrations:
    """
    Container for tracer concentrations and their metadata.

    The normalized data is stored in :attr:`cv` as a defensive copy. Input
    tables must contain ``element``, ``concentration`` and ``date``. Missing
    ``error`` and ``unit`` columns default to zero and ``"mol/l"`` respectively.
    Extra columns are deliberately discarded at this package boundary.
    """

    def __init__(self, frame: pd.DataFrame) -> None:
        """Normalize and validate a copy of an observation dataframe."""
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("frame must be a pandas DataFrame")
        self.cv = frame.copy().reset_index(drop=True)
        self.__ensure_column(ERROR_COLUMN, _DEFAULT_ERROR)
        self.__ensure_column(UNIT_COLUMN, _DEFAULT_UNIT)
        self.validate()

    @classmethod
    def from_file(cls, path: str | Path) -> "Concentrations":
        """Load observations from a UTF-8 tab-separated file."""
        return cls(pd.read_table(Path(path), sep="\t", header=0, encoding="utf-8"))

    @classmethod
    def from_dataframe(cls, frame: pd.DataFrame) -> "Concentrations":
        """Build observations from an existing dataframe copy."""
        return cls(frame)

    def error_affect_from_mean(
        self, mean_value: Iterable[float], fraction: float = 0.01
    ) -> None:
        """
        Assign errors proportional to mean tracer concentrations.

        Only rows whose current error is exactly zero are updated. Existing
        positive errors are preserved.

        Parameters
        ----------
        mean_value : iterable of float
            One finite, non-negative mean value for each observation row.
        fraction : float, default 0.01
            Non-negative fraction of the mean value used as error.

        Raises
        ------
        ValueError
            If the fraction or mean values cannot define valid errors.
        """
        fraction = self._validate_fraction(fraction)
        mean_array = np.asarray(mean_value, dtype=float)
        if mean_array.shape != (len(self.cv),):
            raise ValueError(
                "mean_value must contain exactly one value per concentration row "
                f"({len(self.cv)} expected, received {mean_array.size})"
            )
        if not np.all(np.isfinite(mean_array)) or np.any(mean_array < 0.0):
            raise ValueError("mean_value entries must be finite and non-negative")
        missing_error = self.cv[ERROR_COLUMN].to_numpy(dtype=float) == 0.0
        self.cv.loc[missing_error, ERROR_COLUMN] = mean_array[missing_error] * fraction

    def error_affect_from_value(self, fraction: float) -> None:
        """
        Assign errors proportional to concentration values.

        The absolute concentration is used so that a valid uncertainty remains
        non-negative even when an analytical observation is below zero.

        Parameters
        ----------
        fraction : float
            Non-negative fraction of the concentration magnitude used as error.
        """
        fraction = self._validate_fraction(fraction)
        values = self.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        self.cv[ERROR_COLUMN] = fraction * np.abs(values)

    @staticmethod
    def _validate_fraction(fraction: float) -> float:
        """Return a finite, non-negative error fraction."""
        if isinstance(fraction, bool) or not isinstance(fraction, Real):
            raise TypeError("fraction must be a real number")
        normalized = float(fraction)
        if not np.isfinite(normalized) or normalized < 0.0:
            raise ValueError("fraction must be finite and non-negative")
        return normalized

    def __ensure_column(self, name: str, default_value) -> None:
        """Ensure a column exists in cv; insert a default when missing."""
        if name not in self.cv.columns:
            self.cv[name] = default_value

    def validate(self) -> None:
        """Validate values and normalize the table to the canonical schema."""
        duplicate_columns = self.cv.columns[self.cv.columns.duplicated()].tolist()
        if duplicate_columns:
            raise ValueError(
                "Duplicate concentration columns are not allowed: "
                + ", ".join(map(str, duplicate_columns))
            )
        missing = [column for column in REFERENCE_COLUMNS if column not in self.cv]
        if missing:
            raise ValueError(
                "Missing required columns in concentrations: " + ", ".join(missing)
            )
        if self.cv.empty:
            raise ValueError("Concentrations must contain at least one observation")

        normalized = self.cv.loc[:, list(REFERENCE_COLUMNS)].copy()
        for column in (CONCENTRATION_COLUMN, ERROR_COLUMN, DATE_COLUMN):
            try:
                normalized[column] = pd.to_numeric(normalized[column], errors="raise")
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Concentration column {column!r} must contain numeric values"
                ) from exc
            values = normalized[column].to_numpy(dtype=float)
            if not np.all(np.isfinite(values)):
                raise ValueError(
                    f"Concentration column {column!r} must contain only finite values"
                )

        if np.any(normalized[ERROR_COLUMN].to_numpy(dtype=float) < 0.0):
            raise ValueError("Concentration errors must be non-negative")

        if normalized[ELEMENT_COLUMN].isna().any():
            raise ValueError("Concentration elements must not be missing")
        normalized[ELEMENT_COLUMN] = normalized[ELEMENT_COLUMN].astype(str)
        if normalized[ELEMENT_COLUMN].str.strip().eq("").any():
            raise ValueError("Concentration elements must not be empty")

        normalized[UNIT_COLUMN] = (
            normalized[UNIT_COLUMN].fillna(_DEFAULT_UNIT).astype(str)
        )
        self.cv = normalized.reset_index(drop=True)

    def sample_concentrations_with_errors(
        self, rng: np.random.Generator
    ) -> "Concentrations":
        """
        Sample independent Gaussian observation errors.

        Parameters
        ----------
        rng : numpy.random.Generator
            Random number generator controlling reproducibility.

        Returns
        -------
        Concentrations
            A new container; the source observations are not modified.
        """
        if not isinstance(rng, np.random.Generator):
            raise TypeError("rng must be a numpy.random.Generator")
        sampled = self.from_dataframe(self.cv)
        draw = rng.standard_normal(size=len(sampled.cv))
        base = self.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        err = self.cv[ERROR_COLUMN].to_numpy(dtype=float)
        sampled.cv[CONCENTRATION_COLUMN] = base + err * draw
        return sampled

    def display(self, display_options: DisplayOptions) -> None:
        """Display the concentration table when text output is enabled."""
        if display_options.text:
            print(self.cv)

    def figure_concentrations(
        self,
        i1: int,
        i2: int,
        label_x: str | None = None,
        label_y: str | None = None,
        *,
        ax: Axes | None = None,
    ) -> PathCollection:
        """Plot two concentration values by zero-based row index.

        Returns the Matplotlib artist so callers can further customize it.
        """
        if (
            isinstance(i1, bool)
            or isinstance(i2, bool)
            or not isinstance(i1, int)
            or not isinstance(i2, int)
            or i1 < 0
            or i2 < 0
            or i1 >= len(self.cv)
            or i2 >= len(self.cv)
        ):
            raise IndexError("Index out of range for concentration plot.")
        target = ax if ax is not None else plt.gca()
        artist = target.scatter(
            self.cv[CONCENTRATION_COLUMN].iloc[i1],
            self.cv[CONCENTRATION_COLUMN].iloc[i2],
            marker="o",
            c="r",
            s=150,
        )
        if label_x:
            target.set_xlabel(label_x)
        if label_y:
            target.set_ylabel(label_y)
        return artist

    def names(self) -> list[str]:
        """Return tracer names as a list."""
        return self.cv[ELEMENT_COLUMN].tolist()

    def names_dates(self) -> list[str]:
        """Return tracer names combined with date and index."""
        return [
            f"{element}_{date}_{index}"
            for index, (element, date) in enumerate(
                zip(
                    self.cv[ELEMENT_COLUMN],
                    self.cv[DATE_COLUMN],
                    strict=True,
                )
            )
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
        cv[ELEMENT_COLUMN] = [
            name_date(element, date)
            for element, date in zip(
                cv[ELEMENT_COLUMN],
                cv[DATE_COLUMN],
                strict=True,
            )
        ]
        return cv
