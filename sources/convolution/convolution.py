# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
This module implements numerical convolution between tracer recharge
chronicles and Lumped Parameter Model (LPM) transit time distributions.
It provides a `Convolution` class that loads tracer data, evaluates
convolutions at a given date, and supports specialized algorithms for
Dirac, exponential, and mixed distributions. The code is used in
calibration workflows to compute modeled concentrations from LPM
parameters, and can also produce concentration time series over a date
range for analysis and plotting.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import integrate

import global_parameters as gp
import tracer.tracer_root as tracer

if TYPE_CHECKING:
    from pathlib import Path
    from LPM.core.LPM_root import LPM

# LPM type sets for convolution dispatch
LPM_DIRAC_TYPES = {"dirac", "dirac_double", "dirac_double_1_set"}
LPM_EXP_TYPES = {"exp", "exp_shifted", "exp_shifted_young", "exp_shifted_old"}
LPM_IG_TYPES = {"ig","ig_shifted"}
LPM_SPECIAL_TYPES = LPM_DIRAC_TYPES | LPM_EXP_TYPES | {"mix_exp_shifted"}


class ConvolutionError(Exception):
    """Exception raised for convolution preparation/execution errors."""
    pass


class Convolution(tracer.Tracer):
    """
    Convolution of a Tracer with a Lumped Parameter Model (LPM).

    Performs numerical convolution between tracer recharge chronicles and
    transit time distributions (LPM) for groundwater age dating applications.

    Attributes
    ----------
    date : float
        Date (year) at which the convolution is performed.

    Methods
    -------
    convolution
        Compute convolution between tracer and LPM at the configured date.
    convolution_prepare
        Pre-compute convolution data for classic distributions.
    convolution_date_range
        Compute convolution over a range of dates.

    Private Methods
    ---------------
    __convolution_classic_prepare
        Prepare convolution sampling for classic distributions.
    __convolution_classic_perform
        Execute prepared convolution using Simpson integration.
    __convolution_exp
        Convolution for exponential distributions with adapted discretization.
    __convolution_dirac
        Convolution for Dirac distributions via direct chronicle lookup.
    __convolution_mix_exp_shifted
        Convolution for mixed Dirac and shifted exponential distributions.
    __apply_age_correction
        Apply penalty correction for young/old distribution constraints.

    Examples
    --------
        >>> conv = Convolution(dir_tracer, name="cfc11", date=2010)
        >>> result = conv.convolution(lpm)

    Notes
    -----
        Different LPM types use specialized convolution algorithms:
        - Dirac: direct chronicle lookup
        - Exponential: adapted discretization near discontinuity
        - Classic (uniform, ig, gamma): standard numerical integration

    Raises
    ------
    ConvolutionError
        If preparation state is inconsistent with execution parameters.
    """

    def __init__(
        self,
        dir_tracer: Path = gp.DIRECTORY_TRACER_DATA,
        name: str = "",
        date: float = 2010
    ) -> None:
        """
        Initialize Convolution from tracer data.

        Parameters
        ----------
        dir_tracer : Path
            Root directory containing tracer data files.
        name : str
            Tracer name (e.g., 'cfc11', 'kr85').
        date : float
            Date (year) at which convolution will be computed.
            Possibly one date per tracer, that's why it is stored in this class.
        """
        self.__date: float = date
        self.__prepare_times: npt.NDArray[np.floating] | list = []
        self.__prepare_conc: npt.NDArray[np.floating] | list = []
        self.__prepare: bool = False
        super().__init__(dir_tracer, name)


    @property


    def date(self) -> float:
        """Date (year) at which convolution is performed."""
        return self.__date


    def __convolution_classic_prepare(self, lpm_type: str) -> None:
        """
        Prepare convolution sampling between datemin and current date.

        Parameters
        ----------
        lpm_type : str
            LPM type name, used to determine sampling resolution.
        """
        if lpm_type in LPM_IG_TYPES:
            resolution = gp.RESOLUTION_CONVOLUTION
        else:
            resolution = min(25 * gp.RESOLUTION_CONVOLUTION, 5000)
        dates = self.datemin + (self.__date - self.datemin) * np.arange(0, 1, 1 / resolution)
        self.__prepare_times = self.__date - dates
        self.__prepare_conc = self.get_concentration(dates, self.__date - dates)


    def __convolution_classic_perform(self, lpm: LPM) -> float:
        """
        Execute prepared convolution using Simpson integration.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model providing the PDF.

        Returns
        -------
        float
            Convolution result (tracer concentration).
        """
        return -integrate.simpson(
            self.__prepare_conc * lpm.pdf(self.__prepare_times),
            x=self.__prepare_times
        )


    def __convolution_exp(self, lpm: LPM) -> float:
        """
        Convolution for exponential distributions.

        Uses adapted discretization starting at the distribution discontinuity,
        with refined sampling close to the discontinuity.

        Parameters
        ----------
        lpm : LPM
            Exponential-type LPM (exp, exp_shifted, etc.).

        Returns
        -------
        float
            Convolution result (tracer concentration).
        """
        shift = 0.0 if lpm.name == "exp" else lpm.p["shift"]
        maxdate = self.__date - shift

        if maxdate < self.datemin:
            return 0.0

        sampling = (np.arange(0, 1, 1 / gp.RESOLUTION_CONVOLUTION)) ** 4
        t2 = maxdate - (maxdate - self.datemin) * sampling
        return -integrate.simpson(
            self.get_concentration(t2, self.__date - t2) * lpm.pdf(self.__date - t2),
            x=t2
        )


    def __convolution_dirac(self, lpm: LPM) -> float:
        """
        Convolution for Dirac distributions via direct chronicle lookup.

        Parameters
        ----------
        lpm : LPM
            Dirac-type LPM (dirac, dirac_double, etc.).

        Returns
        -------
        float
            Convolution result (tracer concentration).
        """
        if lpm.name in {"dirac", "mix_exp_shifted"}:
            # Specific case for which convolution is determined by picking up a value in the chronicle
            time = lpm.get_dirac_time()
            convol = self.get_concentration(self.__date - time, time)
        elif lpm.name in {"dirac_double", "dirac_double_1_set"}:
            [time1, time2] = lpm.get_dirac_double_time()
            convol1 = self.get_concentration(self.__date - time1, time1)
            convol2 = self.get_concentration(self.__date - time2, time2)
            convol = lpm.p['rate'] * convol1 + (1 - lpm.p['rate']) * convol2
        return convol


    def __convolution_mix_exp_shifted(self, lpm: LPM) -> float:
        """
        Convolution for mixed Dirac and shifted exponential distributions.

        Parameters
        ----------
        lpm : LPM
            Mixed LPM with 'rate' parameter for Dirac/exponential weighting.

        Returns
        -------
        float
            Weighted sum of Dirac and exponential convolution.
        """
        return lpm.p["rate"] * self.__convolution_dirac(lpm) + (1 - lpm.p["rate"]) * self.__convolution_exp(lpm)


    def convolution_prepare(self, lpm_type: str) -> None:
        """
        Pre-compute convolution data for classic distributions.

        Parameters
        ----------
        lpm_type : str
            LPM type name. Special types (Dirac, exponential) are skipped.
        """
        if lpm_type not in LPM_SPECIAL_TYPES:
            self.__convolution_classic_prepare(lpm_type)
            self.__prepare = True


    def convolution(
        self,
        lpm: LPM,
        prepare: bool = False,
        reg: bool = False,
        opt: bool = False
    ) -> float:
        """
        Compute convolution between tracer and LPM at the configured date.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model defining the transit time distribution.
        prepare : bool
            Expected preparation state for consistency check.
            False: prepare and perform convolution.
            True: perform only (preparation completed previously).
        reg : bool
            Internal flag to prevent recursive age correction.
        opt : bool
            Enable age correction for young/old distributions during optimization.

        Returns
        -------
        float
            Convolution result (tracer concentration).

        Raises
        ------
        ConvolutionError
            If preparation state is inconsistent with prepare parameter.
        """
        # Dispatch by LPM type
        dispatch = {
            **{t: self._Convolution__convolution_dirac for t in LPM_DIRAC_TYPES},
            **{t: self._Convolution__convolution_exp for t in LPM_EXP_TYPES},
            "mix_exp_shifted": self._Convolution__convolution_mix_exp_shifted,
        }

        if lpm.name in dispatch:
            convol = dispatch[lpm.name](lpm)
        else:
            # Classic convolution with preparation check
            if self.__prepare != prepare:
                raise ConvolutionError(
                    f"Inconsistent preparation state: prepare={prepare}, "
                    f"but __prepare={self.__prepare}"
                )
            if not self.__prepare:
                self.__convolution_classic_prepare(lpm.name)
            convol = self.__convolution_classic_perform(lpm)
        
        if opt and not reg:
            convol = self.__apply_age_correction(convol, lpm, prepare)

        return convol


    def __apply_age_correction(
        self,
        convol: float,
        lpm: LPM,
        prepare: bool
    ) -> float:
        """
        Apply penalty correction for young/old distribution constraints.

        When distribution is shifted upwards (in time), it ages.
        If the shifted convolution shows the distribution is on the wrong side,
        penalize the objective function to guide optimization.

        Parameters
        ----------
        convol : float
            Original convolution result.
        lpm : LPM
            LPM with name ending in 'young' or 'old'.
        prepare : bool
            Preparation state for recursive convolution call.

        Returns
        -------
        float
            Corrected convolution result (penalized if on wrong side).
        """
        is_young = lpm.name.endswith('young')
        is_old = lpm.name.endswith('old')

        if not (is_young or is_old):
            return convol

        lpm2 = copy.deepcopy(lpm)
        lpm2.shift_upward()
        convol2 = self.convolution(lpm2, prepare, reg=True)

        # Young: convol2 should be >= convol (aging increases concentration)
        # Old: convol2 should be <= convol (aging decreases concentration)
        wrong_side = (is_young and convol2 < convol) or (is_old and convol2 > convol)

        if wrong_side:
            convol = 200 * self.max_value() - convol

        return convol


    def convolution_date_range(
        self,
        lpm: LPM,
        date1: float,
        date2: float
    ) -> pd.DataFrame:
        """
        Compute convolution over a range of dates.

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
        pd.DataFrame
            DataFrame with columns: 'date', 'concentration', 'element'.
        """
        resolution = 50
        date = gp.arange_n(date1, date2, resolution)
        conc = []
        for i in date:
            self.__date = i
            conc.append(self.convolution(lpm))
        data = [date, conc]
        df = pd.DataFrame(data=data)
        df = df.T
        df.columns = ['date', 'concentration']
        df['element'] = self.name
        return df
