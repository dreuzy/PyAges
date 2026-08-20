# -*- coding: utf-8 -*-
"""
Concentration data container and helpers.

Provides a lightweight wrapper around a pandas DataFrame to load, validate,
sample, and export tracer concentration data used by calibration workflows.

Copyright (c) 2025 Jean-Raynald de Dreuzy, CNRS
"""

from __future__ import annotations

import copy as copy
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pyage.concentrations.schema import (
    CONCENTRATION_COLUMN,
    ELEMENT_COLUMN,
    ERROR_COLUMN,
    REFERENCE_COLUMNS,
)


def name_date(name: str, date: float) -> str:
    """Build a stable key from a tracer name and date."""
    temp = name + "-" + str("{:.{}f}".format(date, 1))
    temp = temp.replace(".", "_")
    return temp


class Concentrations:
    """
    Container for tracer concentrations and their metadata.

    The underlying data is stored in `cv` (a pandas DataFrame) with reference
    columns defined by `REFERENCE_COLUMNS` (e.g. element, concentration,
    error, unit, date).
    """

    def __init__(
        self,
        file_load: bool = False,
        file_name: str = "",
        dataframe_load: bool = False,
        dataframe_concentration: pd.DataFrame | None = None,
    ) -> None:
        """
        Initialize a Concentrations container.

        Args:
            file_load: Load concentrations from a file if True.
            file_name: Path to the file to load when file_load is True.
            dataframe_load: Load concentrations from a DataFrame if True.
            dataframe_concentration: DataFrame holding concentration data.
        """
        if file_load and dataframe_load:
            raise ValueError("Choose either file_load or dataframe_load, not both")
        if file_load:
            # Loads data from file.
            self.__load_file(file_name)
        elif dataframe_load:
            # Concentrations from dataframe.
            if dataframe_concentration is None:
                raise ValueError(
                    "dataframe_concentration is required when dataframe_load=True"
                )
            self.cv = dataframe_concentration.copy()
        else:
            raise ValueError("Set file_load=True or dataframe_load=True")
        # Definition of errors
        self.__error_definition()
        # Definition of units
        self.__unit_definition()
        # Checks consistency of the data
        self.validate()

    @classmethod
    def from_file(cls, path: str | Path) -> "Concentrations":
        """Load observations from a tab-separated file."""
        return cls(file_load=True, file_name=str(path))

    @classmethod
    def from_dataframe(cls, frame: pd.DataFrame) -> "Concentrations":
        """Build observations from an existing dataframe copy."""
        return cls(dataframe_load=True, dataframe_concentration=frame)

    def __load_file(self, file_name: str) -> None:
        """
        Load concentrations data from a tab-separated file.

        Args:
            file_name: Path to the data file.
        """
        # Creates and reads data
        self.cv = pd.read_table(file_name, sep="\t", header=0)

    def __error_definition(self) -> None:
        """
        Ensure an error column exists; default to zeros.
        """
        self.__ensure_column("error", 0)

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

    def __unit_definition(self) -> None:
        """
        Ensure a unit column exists; default to mol/l.
        """
        self.__ensure_column("unit", "mol/l")

    def __ensure_column(self, name: str, default_value) -> None:
        """Ensure a column exists in cv; insert a default when missing."""
        if name not in self.cv.columns:
            self.cv[name] = default_value

    def __check_consistency(self, strict: bool = False) -> List[str]:
        """
        Check column consistency and enforce column order.

        Ensures all reference columns exist, then reorders columns to the
        canonical order in `REFERENCE_COLUMNS`.
        """
        # Checks the column names
        error = 0
        missing = []
        for column in REFERENCE_COLUMNS:
            if column not in self.cv.columns:
                print(
                    "\nColumn named is not defined and should be\t",
                    column,
                )
                error = 1
                missing.append(column)
        if error:
            print("critical error in the definition of concentrations")
            print("missing columns:", ", ".join(missing))
            if strict:
                raise ValueError(
                    "Missing required columns in concentrations: " + ", ".join(missing)
                )
        # Ensure columns are in the expected order for downstream code.
        self.cv = self.cv[list(REFERENCE_COLUMNS)]
        return missing

    def validate(self, strict: bool = False) -> List[str]:
        """Validate column consistency and optionally raise on errors."""
        return self.__check_consistency(strict=strict)

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
        conc = copy.deepcopy(self)
        # Vectorized draw for all rows.
        draw = rng.standard_normal(size=len(conc.cv))
        base = self.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        err = self.cv[ERROR_COLUMN].to_numpy(dtype=float)
        conc.cv[CONCENTRATION_COLUMN] = base + err * draw
        return conc

    def sqrt_quadratic_mean_diff(self, c2: "Concentrations") -> float:
        """
        Computes sqrt of quadratic mean differnces of self.cv and c2.cv

        Args:
            c2: Concentrations with the same structure as self.

        Returns:
            float: Root mean quadratic difference.
        """
        values = self.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        other = c2.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        return float(np.sqrt(np.mean(np.square(values - other))))

    def display(self, display_options) -> None:
        """Display the concentration table when text output is enabled."""
        if display_options.text:
            print(self.cv)

    def figure_concentrations(
        self,
        i1: int,
        i2: int,
        label_x: Optional[str] = None,
        label_y: Optional[str] = None,
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

    def names(self) -> List[str]:
        """Return tracer names as a list."""
        return [self.cv.iloc[i, 0] for i in range(len(self.cv.iloc[:, 0]))]

    def names_dates(self) -> List[str]:
        """Return tracer names combined with date and index."""
        return [
            self.cv.iloc[i, 0] + "_" + str(self.cv.loc[i]["date"]) + "_" + str(i)
            for i in range(len(self.cv.iloc[:, 0]))
        ]

    def names_list(self, sep: str = "_", prefix: bool = True) -> str:
        """
        Return tracer names concatenated into a single string.

        Args:
            sep: Separator between tracer names.
            prefix: If True, prepend the separator to the result.
        """
        names = self.names()
        if not names:
            return ""
        joined = sep.join(names)
        return f"{sep}{joined}" if prefix else joined

    def export_to_dict(self) -> Dict[str, float]:
        """Export concentrations to a {name: concentration} dict."""
        return dict(zip(self.cv[ELEMENT_COLUMN], self.cv[CONCENTRATION_COLUMN]))

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
