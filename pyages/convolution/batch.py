# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Coordinate convolution for an ordered collection of groundwater tracers.

This module delegates all numerical work to :class:`Convolution`; it binds one
sampling date to each tracer and formats the resulting concentrations.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TextIO

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
    from pyages.lpm.core.lpm_base import LpmBase


class ConvolutionTracers:
    """Prepare and evaluate several independent tracer convolutions.

    The order supplied at construction is preserved in every list or tabular
    result. Each tracer owns its own :class:`Convolution`, including its
    observation date, prepared grid, and latest diagnostics.
    """

    def __init__(
        self,
        names: Iterable[str] | None = None,
        date: float | Iterable[float] = 2010,
        tracer_data_dir: str | Path | None = None,
        grid_settings: TracerGridSettings | None = None,
    ) -> None:
        """Load named tracers and bind each one to its sampling date.

        A scalar ``date`` is broadcast to all tracers. An iterable must contain
        exactly one date per name so that no tracer/date association can be
        silently dropped.
        """
        names = list(names) if names is not None else ["cfc11", "kr85"]
        dates = self._normalize_dates(date, len(names))
        resolved_tracer_dir = (
            Path(tracer_data_dir)
            if tracer_data_dir is not None
            else DIRECTORY_TRACER_DATA
        )
        self.convolutions: list[Convolution] = [
            Convolution(
                Tracer(resolved_tracer_dir, name),
                date=tracer_date,
                grid_settings=grid_settings,
            )
            for name, tracer_date in zip(names, dates, strict=True)
        ]

    @staticmethod
    def _normalize_dates(date: float | Iterable[float], size: int) -> list[float]:
        """Broadcast a scalar date or validate a one-to-one date sequence."""
        if np.isscalar(date):
            return [date] * size
        dates = list(date)
        if len(dates) != size:
            raise ValueError(f"Expected {size} tracer dates, received {len(dates)}")
        return dates

    def display(self, display_options: DisplayOptions) -> None:
        """Display every underlying tracer."""
        for convolution in self.convolutions:
            convolution.tracer.display(display_options)

    def write_name(self, file: TextIO) -> None:
        """Write tracer names to file."""
        file.write("tracers")
        for name in self.tracer_names():
            file.write("\t")
            file.write(name)
        file.write("\n")

    def tracer_names(self) -> list[str]:
        """Return tracer names in convolution order."""
        return [convolution.tracer.name for convolution in self.convolutions]

    def tracer_date_keys(self) -> list[str]:
        """Return canonical tracer/date keys in convolution order."""
        return [
            tracer_date_key(convolution.tracer.name, convolution.date)
            for convolution in self.convolutions
        ]

    def mean_values_at_sampling_dates(self) -> list[float]:
        """Return one tracer mean evaluated at each bound sampling date."""
        return [
            convolution.tracer.mean_value(convolution.date)
            for convolution in self.convolutions
        ]

    def prepare(self, lpm: LpmBase | None = None) -> None:
        """Eagerly prepare only the grids needed by ``lpm``.

        Point-mass strategies perform direct tracer lookups and need no grid.
        With ``lpm=None``, all grids are prepared for callers that want to pay
        the tracer-grid cost before a calibration loop.
        """
        if lpm is not None and lpm.convolution_strategy not in {
            ConvolutionStrategy.CONTINUOUS,
            ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS,
        }:
            return
        for convolution in self.convolutions:
            convolution.prepare()

    def units(self) -> list[str]:
        """Return tracer units in convolution order."""
        return [convolution.tracer.unit for convolution in self.convolutions]

    def validate_observation_units(self, observations: Concentrations) -> None:
        """Validate observation/model units once before numerical work."""
        expected_units = dict(zip(self.tracer_names(), self.units(), strict=True))
        observations.require_matching_units(expected_units)

    def convolve(
        self,
        lpm: LpmBase,
        return_type: Literal["array", "concentrations", "dataframe"] = "array",
    ) -> list[float] | Concentrations | pd.DataFrame:
        """
        Convolve one LPM with every tracer at its configured date.

        Numerical evaluation always follows construction order. ``return_type``
        is validated before any convolution starts, avoiding partially updated
        grids or diagnostics for an invalid output request.

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
            If ``return_type`` is not recognized.
        """
        if return_type not in {"array", "concentrations", "dataframe"}:
            raise ValueError(f"Unknown return_type: {return_type}")

        values = [convolution.convolve(lpm) for convolution in self.convolutions]

        if return_type == "array":
            return values
        if return_type == "concentrations":
            frame = pd.DataFrame(
                {
                    "element": self.tracer_names(),
                    "concentration": values,
                    "unit": self.units(),
                    "date": [convolution.date for convolution in self.convolutions],
                },
                columns=["element", "concentration", "unit", "date"],
            )
            return Concentrations.from_dataframe(frame)
        return pd.DataFrame(
            {
                "element": self.tracer_names(),
                "concentration": values,
            },
            columns=["element", "concentration"],
        )

    def convolve_date_range(
        self,
        lpm: LpmBase,
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

        Raises
        ------
        ValueError
            If a tracer name occurs more than once, because a name-keyed
            dictionary cannot represent duplicate entries without data loss.
        """
        counts = Counter(self.tracer_names())
        # A name-keyed result cannot retain two series with the same name.
        # Reject that ambiguity before any (potentially expensive) convolution.
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(
                "convolve_date_range requires unique tracer names; duplicates: "
                + ", ".join(duplicates)
            )
        return {
            convolution.tracer.name: convolution.convolve_date_range(
                lpm,
                date1,
                date2,
                resolution=resolution,
            )
            for convolution in self.convolutions
        }


__all__ = ["ConvolutionTracers"]
