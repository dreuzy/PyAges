# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Batch convolution of multiple groundwater tracers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from pyages.concentrations import Concentrations
from pyages.concentrations.schema import tracer_date_key
from pyages.config.paths import DIRECTORY_TRACER_DATA
from pyages.config.runtime import DisplayOptions
from pyages.convolution.convolution import Convolution
from pyages.convolution.settings import TracerGridSettings
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.tracer.tracer_root import Tracer

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase as LPM


class ConvolutionTracers:
    """Prepare and evaluate a collection of tracer convolutions."""

    def __init__(
        self,
        names: Iterable[str] | None = None,
        date: float | Iterable[float] = 2010,
        tracer_data_dir: str | Path | None = None,
        grid_settings: TracerGridSettings | None = None,
    ) -> None:
        """Load named tracers and bind each one to its sampling date."""
        names = list(names) if names is not None else ["cfc11", "kr85"]
        dates = self._normalize_dates(date, len(names))
        resolved_tracer_dir = (
            Path(tracer_data_dir)
            if tracer_data_dir is not None
            else DIRECTORY_TRACER_DATA
        )
        self.elements: list[Convolution] = [
            Convolution(
                Tracer(resolved_tracer_dir, name),
                date=tracer_date,
                grid_settings=grid_settings,
            )
            for name, tracer_date in zip(names, dates, strict=True)
        ]

    @staticmethod
    def _normalize_dates(date: float | Iterable[float], size: int) -> list[float]:
        if np.isscalar(date):
            return [float(date)] * size
        dates = [float(value) for value in date]
        if len(dates) != size:
            raise ValueError(f"Expected {size} tracer dates, received {len(dates)}")
        return dates

    def display(self, display_options: DisplayOptions) -> None:
        """Displays the tracers."""
        for x in self.elements:
            x.display(display_options)

    def write_name(self, file) -> None:
        """Write tracer names to file."""
        file.write("tracers")
        for t in self.element_names():
            file.write("\t")
            file.write(t)
        file.write("\n")

    def element_names(self) -> list[str]:
        """Gets the list of element names."""
        return [x.name for x in self.elements]

    def tracer_date_keys(self) -> list[str]:
        """Return canonical tracer/date keys in convolution order."""
        return [tracer_date_key(x.name, x.date) for x in self.elements]

    def mean_value(self, date: float) -> list[float]:
        """
        Mean value of chronicle taken at date.

        Parameters
        ----------
        date : float
            Reference date for computing the mean.

        Returns
        -------
        list[float]
            Mean value for each element concentration.
        """
        return [x.mean_value(date) for x in self.elements]

    def prepare(self, lpm: LPM | None = None) -> None:
        """Eagerly prepare grids when the requested LPM has a continuous part."""
        if lpm is not None and lpm.convolution_strategy not in {
            ConvolutionStrategy.CONTINUOUS,
            ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS,
        }:
            return
        for t in self.elements:
            t.prepare()

    def units(self) -> list[str]:
        """Gets units of tracers."""
        return [t.unit for t in self.elements]

    def convolve(
        self,
        lpm: LPM,
        return_type: Literal["array", "concentrations", "dataframe"] = "array",
    ) -> list[float] | Concentrations | pd.DataFrame:
        """
        Convolution between a LPM and the tracers at configured dates.

        Parameters
        ----------
        lpm : LPM
            LPM with which convolution is made.
        return_type : str
            Format of convolution return:
            - "array": list of concentrations
            - "concentrations": Concentrations object
            - "dataframe": DataFrame with element/concentration columns
        Returns
        -------
        list[float] | Concentrations | pd.DataFrame
            Convolution results in the requested format.

        Raises
        ------
        ValueError
            If return_type is not recognized.
        """
        values = [t.convolve(lpm) for t in self.elements]

        if return_type == "array":
            return values
        if return_type == "concentrations":
            frame = pd.DataFrame(
                {
                    "element": self.element_names(),
                    "concentration": values,
                    "unit": self.units(),
                    "date": [tracer.date for tracer in self.elements],
                },
                columns=["element", "concentration", "unit", "date"],
            )
            return Concentrations.from_dataframe(frame)
        if return_type == "dataframe":
            return pd.DataFrame(
                {
                    "element": self.element_names(),
                    "concentration": values,
                },
                columns=["element", "concentration"],
            )
        raise ValueError(f"Unknown return_type: {return_type}")

    def convolve_date_range(
        self,
        lpm: LPM,
        date1: float,
        date2: float,
        *,
        resolution: int = 50,
    ) -> dict[str, pd.DataFrame]:
        """
        Convolution on the range of dates given by [date1, date2].

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model for convolution.
        date1 : float
            Start date (year).
        date2 : float
            End date (year).
        resolution : int
            Number of equal intervals, shared by every tracer.

        Returns
        -------
        dict[str, pd.DataFrame]
            Dictionary mapping tracer names to their convolution DataFrames.
        """
        return {
            tracer.name: tracer.convolve_date_range(
                lpm,
                date1,
                date2,
                resolution=resolution,
            )
            for tracer in self.elements
        }
