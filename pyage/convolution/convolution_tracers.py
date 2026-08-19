# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
High-level wrapper around multiple tracers for convolution workflows.
Builds and manages a list of `Convolution` instances, dispatches
convolution calls for each tracer, and aggregates results into arrays
or structured outputs (dataframes, Concentrations objects) for
calibration and analysis.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

from pyage.config.paths import DIRECTORY_TRACER_DATA
from pyage.config.runtime import DisplayOptions
import pyage.convolution.convolution as convolution
from pyage.convolution.settings import TracerGridSettings
import pyage.concentrations.concentrations as concentrations
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
import pyage.tracer.tracer_root as tracer_module

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_base import LpmBase as LPM



class ConvolutionTracers:
    """
    Collection of Convolution instances for multiple tracers.

    Manages convolution operations across a set of tracers, providing
    batch operations for preparing and executing convolution.

    Attributes
    ----------
    elements : list[Convolution]
        List of Convolution instances, one per tracer.

    """
    
    def __init__(
        self,
        names: list[str] | None = None,
        date: float | list[float] = 2010,
        tracer_data_dir: str | Path | None = None,
        grid_settings: TracerGridSettings | None = None,
    ) -> None:
        """
        Constructor

        Arguments
        ---------
        names: array of str
            name of tracers to be loaded
        """
        if names is None:
            names = ["cfc11", "kr85"]
        resolved_tracer_dir = (
            Path(tracer_data_dir)
            if tracer_data_dir is not None
            else DIRECTORY_TRACER_DATA
        )
        # Create element list and loads each element
        date_temp = [date] * len(names) if np.isscalar(date) else date
        self.elements: list[convolution.Convolution] = [
            convolution.Convolution(
                tracer_module.Tracer(resolved_tracer_dir, name),
                date=date_temp[k],
                grid_settings=grid_settings,
            )
            for k, name in enumerate(names)
        ]
    
    
    def display(self, display_options: DisplayOptions) -> None:
        """Displays the tracers."""
        for x in self.elements:
            x.display(display_options)


    def write_name(self, file) -> None:
        """Write tracer names to file."""
        file.write("tracers")
        for t in self.element_names():
            file.write('\t')
            file.write(t)
        file.write('\n')


    def element_names(self) -> list[str]:
        """Gets the list of element names."""
        return [x.name for x in self.elements]


    def element_names_dates(self) -> list[str]:
        """Gets the list of element names with dates."""
        return [concentrations.name_date(x.name, x.date) for x in self.elements]


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
        apply_age_correction: bool = False,
    ) -> list[float] | concentrations.Concentrations | pd.DataFrame:
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
        apply_age_correction : bool
            Enable age correction for optimization.

        Returns
        -------
        list[float] | Concentrations | pd.DataFrame
            Convolution results in the requested format.

        Raises
        ------
        ValueError
            If return_type is not recognized.
        """
        conc = [
            t.convolve(lpm, apply_age_correction=apply_age_correction)
            for t in self.elements
        ]
        date_vec = [t.date for t in self.elements]

        if return_type == "array":
            return conc
        elif return_type == "concentrations":
            data_temp = pd.DataFrame({
                "element": self.element_names(),
                "concentration": conc,
                "unit": self.units(),
                "date": date_vec
            }, columns=["element", "concentration", "unit", "date"])
            return concentrations.Concentrations(dataframe_load=True, dataframe_concentration=data_temp)
        elif return_type == "dataframe":
            return pd.DataFrame({
                "element": self.element_names(),
                "concentration": conc,
                "date": date_vec
            }, columns=["element", "concentration"])
        else:
            raise ValueError(f"Unknown return_type: {return_type}")
    
    
    def convolve_date_range(
        self,
        lpm: LPM,
        date1: float,
        date2: float
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

        Returns
        -------
        dict[str, pd.DataFrame]
            Dictionary mapping tracer names to their convolution DataFrames.
        """
        return {t.name: t.convolve_date_range(lpm, date1, date2) for t in self.elements}


    
    
    
