# -*- coding: utf-8 -*-
"""
Numerical convolution between tracer chronicles and LPM distributions.

Purpose
-------
This module implements numerical convolution between tracer recharge
chronicles and Lumped Parameter Model (LPM) transit time distributions.
It provides a `Convolution` class that accepts any tracer implementing
the TracerProtocol interface, evaluates convolutions at a given date,
and supports specialized algorithms for Dirac, exponential, and mixed
distributions.

The convolution algorithm is selected based on the LPM's declared
`convolution_strategy` attribute, enabling new LPM types to be added
without modifying this module.

Architecture
------------
This module uses composition over inheritance: Convolution holds a
reference to a tracer (TracerProtocol) rather than inheriting from Tracer.
This enables using any tracer implementation (FileTracer, SyntheticTracer,
ConstantTracer, etc.) without code changes.

Author
------
Jean-Raynald de Dreuzy
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Union

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import integrate

import pyage.global_parameters as gp
from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.tracer.tracer_protocol import TracerProtocol

if TYPE_CHECKING:
    from pathlib import Path
    from pyage.lpm.core.lpm_base import LpmBase as LPM


IG_SHIFTED_PIECEWISE_Q10_THRESHOLD = 0.75
IG_SHIFTED_PIECEWISE_Q50_THRESHOLD = 2.5
IG_SHIFTED_PIECEWISE_SEGMENTS = (
    (0.10, 60, 2.8),
    (0.50, 60, 1.6),
    (0.90, 40, 1.2),
    (0.99, 20, 1.0),
)
IG_SHIFTED_PIECEWISE_TAIL_POINTS = 10


class ConvolutionError(Exception):
    """Exception raised for convolution preparation/execution errors."""
    pass


class Convolution:
    """
    Convolution of a Tracer with a Lumped Parameter Model (LPM).

    Performs numerical convolution between tracer recharge chronicles and
    transit time distributions (LPM) for groundwater age dating applications.

    The convolution algorithm is automatically selected based on the LPM's
    `convolution_strategy` attribute:
    - CLASSIC: Standard numerical integration (Simpson's rule)
    - DIRAC: Direct chronicle lookup for single spike
    - DIRAC_DOUBLE: Weighted combination of two lookups
    - EXPONENTIAL: Adapted discretization near discontinuity
    - MIX_DIRAC_EXPONENTIAL: Weighted Dirac + exponential

    Attributes
    ----------
    tracer : TracerProtocol
        Tracer instance providing concentration data.
    date : float
        Date (year) at which the convolution is performed.

    Examples
    --------
        >>> from pyage.tracer.tracer_root import Tracer
        >>> tracer = Tracer(dir_tracer, name="cfc11")
        >>> conv = Convolution(tracer, date=2010)
        >>> result = conv.convolution(lpm)

        >>> # With synthetic tracer for testing
        >>> from pyage.tracer.tracer_protocol import SyntheticTracer
        >>> synth = SyntheticTracer(concentration_fn=lambda d, t: 100 * np.exp(-t/20))
        >>> conv = Convolution(synth, date=2010)
        >>> result = conv.convolution(lpm)
    """

    def __init__(
        self,
        tracer: TracerProtocol,
        date: float = 2010,
    ) -> None:
        """
        Initialize Convolution with a tracer instance.

        Parameters
        ----------
        tracer : TracerProtocol
            Any tracer implementing the TracerProtocol interface
            (Tracer, SyntheticTracer, ConstantTracer, DecayTracer, etc.).
        date : float
            Date (year) at which convolution will be computed.

        Examples
        --------
            >>> from pyage.tracer.tracer_root import Tracer
            >>> tracer = Tracer(dir_tracer, "cfc11")
            >>> conv = Convolution(tracer, date=2010)

            >>> from pyage.tracer.tracer_protocol import SyntheticTracer
            >>> synth = SyntheticTracer(concentration_fn=lambda d, t: 100 * np.exp(-t/20))
            >>> conv = Convolution(synth, date=2010)
        """
        self._tracer: TracerProtocol = tracer
        self._date: float = date
        self._prepare_times: npt.NDArray[np.floating] | list = []
        self._prepare_conc: npt.NDArray[np.floating] | list = []
        self._prepare: bool = False
        self._prepared_strategy: ConvolutionStrategy | None = None

    @property
    def tracer(self) -> TracerProtocol:
        """Tracer instance providing concentration data."""
        return self._tracer

    @property
    def name(self) -> str:
        """Tracer name (delegated to tracer)."""
        return self._tracer.name

    @property
    def datemin(self) -> float:
        """Minimum valid date (delegated to tracer)."""
        return self._tracer.datemin

    @property
    def datemax(self) -> float:
        """Maximum valid date (delegated to tracer)."""
        return self._tracer.datemax

    @property
    def unit(self) -> str:
        """Concentration unit (delegated to tracer)."""
        return self._tracer.unit

    def mean_value(self, date: float) -> float:
        """
        Mean value of chronicle taken at date (delegated to tracer).

        Parameters
        ----------
        date : float
            Reference date.

        Returns
        -------
        float
            Mean value at the given date.
        """
        if hasattr(self._tracer, 'mean_value'):
            return self._tracer.mean_value(date)
        # Fallback: return concentration at date with time=0
        return float(self._tracer.get_concentration(date, 0.0))

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """Get concentration from tracer (delegated)."""
        return self._tracer.get_concentration(date, time)

    def max_value(self) -> float:
        """Get maximum concentration value from pyage.tracer."""
        # If tracer has max_value method, use it; otherwise estimate
        if hasattr(self._tracer, 'max_value'):
            return self._tracer.max_value()
        # Fallback: sample some values and return max
        times = np.linspace(0, 100, 100)
        concs = self._tracer.get_concentration(self._date - times, times)
        return float(np.max(concs))

    @property
    def date(self) -> float:
        """Date (year) at which convolution is performed."""
        return self._date

    @date.setter
    def date(self, value: float) -> None:
        """Set the date (needed for date range calculations)."""
        self._date = value

    # -------------------------------------------------------------------------
    # Classic convolution (numerical integration)
    # -------------------------------------------------------------------------

    def _convolution_classic_prepare(self, strategy: ConvolutionStrategy) -> None:
        """
        Prepare convolution sampling between datemin and current date.

        Parameters
        ----------
        strategy : ConvolutionStrategy
            Strategy to determine sampling resolution.
        """
        # Higher resolution for IG distributions (smoother near origin)
        if strategy == ConvolutionStrategy.CLASSIC:
            resolution = gp.RESOLUTION_CONVOLUTION
        else:
            resolution = min(25 * gp.RESOLUTION_CONVOLUTION, 5000)

        dates = self.datemin + (self._date - self.datemin) * np.arange(0, 1, 1 / resolution)
        self._prepare_times = self._date - dates
        self._prepare_conc = self._tracer.get_concentration(dates, self._date - dates)

    def _convolution_classic_perform(self, lpm: LPM) -> float:
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
            self._prepare_conc * lpm.pdf(self._prepare_times),
            x=self._prepare_times
        )

    def _ig_shifted_piecewise_profile(self, lpm: LPM) -> dict[str, float] | None:
        """
        Return a piecewise-integration profile for very sharp ig_shifted cases.

        The special path is intentionally narrow: it is only enabled when the
        distribution starts just after the shift and reaches its median quickly.
        Broader ig_shifted cases stay on the regular classic workflow.
        """
        if lpm.name != "ig_shifted":
            return None

        shift = float(lpm.p.get("shift", np.nan))
        if not np.isfinite(shift):
            return None

        q10 = float(lpm.cdf_inv(0.10))
        q50 = float(lpm.cdf_inv(0.50))
        if not (np.isfinite(q10) and np.isfinite(q50)):
            return None
        if (q10 - shift) > IG_SHIFTED_PIECEWISE_Q10_THRESHOLD:
            return None
        if (q50 - shift) > IG_SHIFTED_PIECEWISE_Q50_THRESHOLD:
            return None

        q90 = float(lpm.cdf_inv(0.90))
        q99 = float(lpm.cdf_inv(0.99))
        if not (np.isfinite(q90) and np.isfinite(q99)):
            return None

        return {
            "shift": shift,
            "q10": q10,
            "q50": q50,
            "q90": q90,
            "q99": q99,
        }

    @staticmethod
    def _piecewise_segment(
        start: float,
        end: float,
        npts: int,
        power: float = 1.0,
    ) -> npt.NDArray[np.float64]:
        """Return a monotonic segment with optional clustering near the start."""
        if npts <= 0 or not np.isfinite(start) or not np.isfinite(end) or end <= start:
            return np.array([], dtype=float)
        sampling = np.linspace(0.0, 1.0, npts, endpoint=False)
        return start + (end - start) * np.power(sampling, power)

    def _convolution_ig_shifted_piecewise(
        self,
        lpm: LPM,
        profile: dict[str, float],
    ) -> float:
        """
        Integrate sharp ig_shifted kernels on a piecewise time grid.

        The grid concentrates points between the shift and the main mass of the
        distribution, then relaxes through the long tail.
        """
        tmax = float(self._date - self.datemin)
        shift = max(float(profile["shift"]), 0.0)
        if not np.isfinite(tmax) or tmax <= shift:
            return 0.0

        quantiles = np.array(
            [profile["q10"], profile["q50"], profile["q90"], profile["q99"]],
            dtype=float,
        )
        quantiles = np.clip(quantiles, shift, tmax)
        q10, q50, q90, q99 = np.maximum.accumulate(quantiles)

        grid_parts = []
        current = shift
        for boundary, npts, power in (
            (q10, *IG_SHIFTED_PIECEWISE_SEGMENTS[0][1:]),
            (q50, *IG_SHIFTED_PIECEWISE_SEGMENTS[1][1:]),
            (q90, *IG_SHIFTED_PIECEWISE_SEGMENTS[2][1:]),
            (q99, *IG_SHIFTED_PIECEWISE_SEGMENTS[3][1:]),
        ):
            grid_parts.append(self._piecewise_segment(current, boundary, npts, power=power))
            current = boundary

        grid_parts.append(self._piecewise_segment(current, tmax, IG_SHIFTED_PIECEWISE_TAIL_POINTS))
        grid_parts.append(np.array([tmax], dtype=float))

        times = np.unique(np.concatenate(grid_parts))
        if times.size < 2:
            return 0.0

        concentrations = self.get_concentration(self._date - times, times)
        return float(integrate.simpson(concentrations * lpm.pdf(times), x=times))

    # -------------------------------------------------------------------------
    # Exponential convolution (adapted discretization)
    # -------------------------------------------------------------------------

    def _convolution_exponential(self, lpm: LPM) -> float:
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
        # Get shift parameter (0 for pure exponential)
        shift = lpm.p.get("shift", 0.0)
        maxdate = self._date - shift

        if maxdate < self.datemin:
            return 0.0

        # Power-law sampling for refined discretization near discontinuity
        sampling = (np.arange(0, 1, 1 / gp.RESOLUTION_CONVOLUTION)) ** 4
        t2 = maxdate - (maxdate - self.datemin) * sampling

        return -integrate.simpson(
            self.get_concentration(t2, self._date - t2) * lpm.pdf(self._date - t2),
            x=t2
        )

    # -------------------------------------------------------------------------
    # Dirac convolution (direct lookup)
    # -------------------------------------------------------------------------

    def _convolution_dirac(self, lpm: LPM) -> float:
        """
        Convolution for single Dirac distribution via direct chronicle lookup.

        Parameters
        ----------
        lpm : LPM
            Dirac-type LPM with get_dirac_time() method.

        Returns
        -------
        float
            Convolution result (tracer concentration).
        """
        time = lpm.get_dirac_time()
        return self.get_concentration(self._date - time, time)

    def _convolution_dirac_double(self, lpm: LPM) -> float:
        """
        Convolution for double Dirac distribution.

        Parameters
        ----------
        lpm : LPM
            Double-Dirac LPM with get_dirac_double_time() and 'rate' parameter.

        Returns
        -------
        float
            Weighted sum of two Dirac lookups.
        """
        [time1, time2] = lpm.get_dirac_double_time()
        convol1 = self.get_concentration(self._date - time1, time1)
        convol2 = self.get_concentration(self._date - time2, time2)
        return lpm.p['rate'] * convol1 + (1 - lpm.p['rate']) * convol2

    # -------------------------------------------------------------------------
    # Mixed convolution (Dirac + exponential)
    # -------------------------------------------------------------------------

    def _convolution_mix_dirac_exponential(self, lpm: LPM) -> float:
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
        dirac_part = self._convolution_dirac(lpm)
        exp_part = self._convolution_exponential(lpm)
        return lpm.p["rate"] * dirac_part + (1 - lpm.p["rate"]) * exp_part

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def convolution_prepare(self, strategy: ConvolutionStrategy) -> None:
        """
        Pre-compute convolution data for classic distributions.

        Parameters
        ----------
        strategy : ConvolutionStrategy
            Convolution strategy for the requested LPM.
            Special types (Dirac, exponential) are skipped.
        """
        # Only prepare for CLASSIC strategy (others compute on-the-fly)
        if strategy == ConvolutionStrategy.CLASSIC:
            self._convolution_classic_prepare(strategy)
            self._prepare = True
            self._prepared_strategy = strategy

    def convolution(
        self,
        lpm: LPM,
        prepare: bool = False,
        reg: bool = False,
        opt: bool = False
    ) -> float:
        """
        Compute convolution between tracer and LPM at the configured date.

        The algorithm is automatically selected based on the LPM's
        `convolution_strategy` attribute.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model defining the transit time distribution.
        prepare : bool
            Expected preparation state for consistency check (CLASSIC only).
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
        strategy = lpm.convolution_strategy

        # Dispatch based on strategy
        match strategy:
            case ConvolutionStrategy.DIRAC:
                convol = self._convolution_dirac(lpm)

            case ConvolutionStrategy.DIRAC_DOUBLE:
                convol = self._convolution_dirac_double(lpm)

            case ConvolutionStrategy.EXPONENTIAL:
                convol = self._convolution_exponential(lpm)

            case ConvolutionStrategy.MIX_DIRAC_EXPONENTIAL:
                convol = self._convolution_mix_dirac_exponential(lpm)

            case ConvolutionStrategy.CLASSIC | _:
                piecewise_profile = self._ig_shifted_piecewise_profile(lpm)
                if piecewise_profile is not None:
                    convol = self._convolution_ig_shifted_piecewise(lpm, piecewise_profile)
                else:
                    # Classic convolution with preparation check
                    if self._prepare != prepare:
                        raise ConvolutionError(
                            f"Inconsistent preparation state: prepare={prepare}, "
                            f"but _prepare={self._prepare}"
                        )
                    if not self._prepare:
                        self._convolution_classic_prepare(strategy)
                    convol = self._convolution_classic_perform(lpm)

        # Apply age correction for young/old distributions during optimization
        if opt and not reg:
            convol = self._apply_age_correction(convol, lpm, prepare)

        return convol

    def _apply_age_correction(
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
            self._date = i
            conc.append(self.convolution(lpm))
        data = [date, conc]
        df = pd.DataFrame(data=data)
        df = df.T
        df.columns = ['date', 'concentration']
        df['element'] = self.name
        return df


__all__ = ["Convolution", "ConvolutionError"]
