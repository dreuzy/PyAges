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

import os
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

import global_parameters as gp
import convolution.convolution as convolution
import concentrations.concentrations as concentrations
import tracer.tracer_root as tracer_module

if TYPE_CHECKING:
    from LPM.core.LPM_root import LPM
    from LPM.core.convolution_strategy import ConvolutionStrategy

# Import for test functions only
import LPM.LPM_generate as LPM_generate


class ConvolutionTracers:
    """
    Collection of Convolution instances for multiple tracers.

    Manages convolution operations across a set of tracers, providing
    batch operations for preparing and executing convolution.

    Attributes
    ----------
    elements : list[Convolution]
        List of Convolution instances, one per tracer.

    Methods
    -------
    convolution
        Compute convolution for all tracers with a given LPM.
    convolution_prepare
        Pre-compute convolution data for all tracers.
    convolution_date_range
        Compute convolution over a date range for all tracers.
    element_names
        Get list of tracer names.
    units
        Get list of tracer units.
    """
    
    def __init__(
        self,
        names: list[str] | None = None,
        date: float | list[float] = 2010
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
        # Create element list and loads each element
        date_temp = [date] * len(names) if np.isscalar(date) else date
        self.elements: list[convolution.Convolution] = [
            convolution.Convolution(
                tracer_module.Tracer(gp.DIRECTORY_TRACER_DATA, name),
                date=date_temp[k]
            )
            for k, name in enumerate(names)
        ]
    
    
    def display(self, display_options: gp.display_options) -> None:
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
    
    
    def convolution_prepare(self, strategy: "ConvolutionStrategy") -> None:
        """Prepares convolution for all tracers using the given strategy."""
        for t in self.elements:
            t.convolution_prepare(strategy)


    def units(self) -> list[str]:
        """Gets units of tracers."""
        return [t.unit for t in self.elements]        

    
    def convolution(
        self,
        lpm: LPM,
        return_type: str = "array",
        prepare: bool = False,
        opt: bool = False
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
            - "concentrations_set": Concentrations object
            - "dataframe_columns": DataFrame with tracer names as columns
            - "dataframe": DataFrame with element/concentration columns
        prepare : bool
            Whether convolution was prepared beforehand.
        opt : bool
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
        conc = [t.convolution(lpm, prepare=prepare, opt=opt) for t in self.elements]
        date_vec = [t.date for t in self.elements]

        if return_type == "array":
            return conc
        elif return_type == "concentrations_set":
            data_temp = pd.DataFrame({
                "element": self.element_names(),
                "concentration": conc,
                "unit": self.units(),
                "date": date_vec
            }, columns=["element", "concentration", "unit", "date"])
            return concentrations.Concentrations(dataframe_load=True, dataframe_concentration=data_temp)
        elif return_type == "dataframe_columns":
            data = pd.DataFrame(columns=self.element_names())
            data.loc[len(data.index)] = conc
            return data
        elif return_type == "dataframe":
            return pd.DataFrame({
                "element": self.element_names(),
                "concentration": conc,
                "date": date_vec
            }, columns=["element", "concentration"])
        else:
            raise ValueError(f"Unknown return_type: {return_type}")
    
    
    def convolution_date_range(
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
        return {t.name: t.convolution_date_range(lpm, date1, date2) for t in self.elements}


def write_file_conc_lpm(date,concentrations,lpm,directory):
    """ 
    Write the tracers in the files
    #JR: definition in concentration classes rather than here? 
    """
    # Write date and lpm    
    name_tracers = ""
    for t in concentrations.iloc[:,0]: name_tracers = name_tracers + "_" + t
    root_name = os.path.join(directory,"convol_" + lpm.name + "_" + name_tracers)
    file = open(root_name +" _lpm" + ".txt", "w")
    file.write("date\t")
    file.write(str(date))
    file.write("\n")
    lpm.write(file,open_file=False)
    file.close()
    # Write concentrations
    concentrations.to_csv(root_name +" _concentrations" + ".txt",sep='\t') #, header=None, index=None, sep=',', mode='w')


    
    
    
