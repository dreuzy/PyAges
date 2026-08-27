# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Numerical convolution between tracer chronicles and LPM distributions.

Purpose
-------
This module implements numerical convolution between tracer recharge
chronicles and Lumped Parameter Model (LPM) transit time distributions.
It provides a `Convolution` class that accepts any tracer implementing
the TracerProtocol interface, evaluates convolutions at a given date,
and supports continuous, discrete, and mixed distributions.

The convolution algorithm is selected based on the LPM's declared
`convolution_strategy` attribute, enabling new LPM types to be added
without modifying this module.

Architecture
------------
This module uses composition over inheritance: Convolution holds a
reference to a tracer (TracerProtocol) rather than inheriting from Tracer.
This enables using any tracer implementation (FileTracer, SyntheticTracer,
ConstantTracer, etc.) without code changes.

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

import numpy as np
import numpy.typing as npt
import pandas as pd

from pyages.config.runtime import subdivide_interval
from pyages.convolution.continuous import (
    convolve_prepared_grid,
    prepare_adaptive_grid,
)
from pyages.convolution.models import (
    ConvolutionDiagnostics,
    ConvolutionError,
    PreparedTracerGrid,
)
from pyages.convolution.settings import (
    DEFAULT_TRACER_GRID_SETTINGS,
    TracerGridSettings,
)
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.tracer.tracer_protocol import TracerProtocol

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase as LPM


class Convolution:
    r"""Convolve one tracer response with a transit-time distribution.

    At observation date :math:`t`, the forward model is

    .. math::

       C(t;\theta)=\int_{0}^{t-t_{min}} K(t,\tau)\,dF_\theta(\tau),

    where :math:`\tau` is water age in years, :math:`K` is the complete tracer
    response returned by ``TracerProtocol.get_concentration(t - tau, tau)``,
    and :math:`F_\theta` is the LPM probability measure. ``K`` includes any
    tracer-specific decay or production and retains the tracer concentration
    unit.

    The convolution algorithm is automatically selected based on the LPM's
    `convolution_strategy` attribute:
    - CONTINUOUS: Cached tracer grid with exact CDF masses and first moments
    - DIRAC: Direct chronicle lookup for single spike
    - DIRAC_DOUBLE: Weighted combination of two lookups
    - MIXED_DIRAC_CONTINUOUS: Weighted Dirac + continuous component

    The finite window ``[0, t - datemin]`` is a scientific boundary
    convention: LPM mass older than the recharge chronicle contributes zero
    and is not renormalized. Continuous LPMs use exact bin masses and partial
    first moments on a cached tracer-driven grid; Dirac masses use direct
    lookups, including both endpoints.

    Attributes
    ----------
    tracer : TracerProtocol
        Tracer instance providing concentration data.
    date : float
        Date (year) at which the convolution is performed.

    Examples
    --------
        >>> from pyages.tracer.tracer_root import Tracer
        >>> tracer = Tracer(dir_tracer, name="cfc11")
        >>> conv = Convolution(tracer, date=2010)
        >>> result = conv.convolve(lpm)

        >>> # With synthetic tracer for testing
        >>> from pyages.tracer.tracer_protocol import SyntheticTracer
        >>> synth = SyntheticTracer(concentration_fn=lambda d, t: 100 * np.exp(-t/20))
        >>> conv = Convolution(synth, date=2010)
        >>> result = conv.convolve(lpm)

    See Also
    --------
    pyages.convolution.settings.TracerGridSettings
        Numerical controls whose non-default values should be reported.

    Notes
    -----
    Equations, boundary conventions, and validation links are consolidated in
    ``docs/scientific-methods.md``; implementation history and independent
    comparisons are in ``docs/convolution-method-evolution-report.md``.
    """

    def __init__(
        self,
        tracer: TracerProtocol,
        date: float = 2010,
        grid_settings: TracerGridSettings | None = None,
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
        grid_settings : TracerGridSettings, optional
            Accuracy and safety controls for the cached tracer-response grid.

        Examples
        --------
            >>> from pyages.tracer.tracer_root import Tracer
            >>> tracer = Tracer(dir_tracer, "cfc11")
            >>> conv = Convolution(tracer, date=2010)

            >>> from pyages.tracer.tracer_protocol import SyntheticTracer
            >>> synth = SyntheticTracer(concentration_fn=lambda d, t: 100 * np.exp(-t/20))
            >>> conv = Convolution(synth, date=2010)
        """
        if not isinstance(tracer, TracerProtocol):
            raise TypeError(
                "tracer must implement the complete TracerProtocol contract"
            )
        self._tracer: TracerProtocol = tracer
        self._date: float = date
        self._grid_settings = grid_settings or DEFAULT_TRACER_GRID_SETTINGS
        self._prepared_grid: PreparedTracerGrid | None = None
        self._last_diagnostics: ConvolutionDiagnostics | None = None

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
        return self._tracer.mean_value(date)

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """Get concentration from tracer (delegated)."""
        return self._tracer.get_concentration(date, time)

    def max_value(self) -> float:
        """Get maximum concentration value from pyages.tracer."""
        return self._tracer.max_value()

    @property
    def date(self) -> float:
        """Date (year) at which convolution is performed."""
        return self._date

    @date.setter
    def date(self, value: float) -> None:
        """Set the date (needed for date range calculations)."""
        if value != self._date:
            self._date = value
            self._prepared_grid = None
            self._last_diagnostics = None

    # -------------------------------------------------------------------------
    # CDF/partial-moment convolution (tracer-driven cached grid)
    # -------------------------------------------------------------------------

    def _evaluate_tracer_response(
        self,
        ages: npt.ArrayLike,
    ) -> npt.NDArray[np.float64]:
        """Evaluate K(age), preserving a vector result for scalar tracers."""
        ages_array = np.asarray(ages, dtype=float)
        values = np.asarray(
            self.get_concentration(self._date - ages_array, ages_array),
            dtype=float,
        )
        if values.ndim == 0:
            values = np.full(ages_array.shape, float(values), dtype=float)
        else:
            try:
                values = np.asarray(
                    np.broadcast_to(values, ages_array.shape), dtype=float
                )
            except ValueError as exc:
                raise ConvolutionError(
                    "Tracer response shape does not match the requested age grid: "
                    f"{values.shape} versus {ages_array.shape}"
                ) from exc
        if not np.all(np.isfinite(values)):
            raise ConvolutionError("Tracer response contains non-finite values")
        return values

    def _initial_tracer_age_edges(self) -> npt.NDArray[np.float64]:
        """Build initial bin edges from chronicle nodes when available."""
        tmax = float(self._date - self.datemin)
        if not np.isfinite(tmax) or tmax < 0.0:
            raise ConvolutionError(
                f"Invalid convolution window [0, {tmax}] for date={self._date} "
                f"and datemin={self.datemin}"
            )
        if tmax == 0.0:
            return np.array([0.0], dtype=float)

        dates = self._tracer.convolution_dates

        edges = np.array([0.0, tmax], dtype=float)
        if dates is not None:
            dates_array = np.asarray(dates, dtype=float).reshape(-1)
            ages = self._date - dates_array
            ages = ages[np.isfinite(ages) & (ages > 0.0) & (ages < tmax)]
            if ages.size:
                edges = np.concatenate((edges, ages))
        else:
            initial_bins = int(self._tracer.convolution_initial_bins)
            if initial_bins < 1:
                raise ConvolutionError(
                    "tracer.convolution_initial_bins must be at least 1"
                )
            if initial_bins > self._grid_settings.max_bins:
                raise ConvolutionError(
                    "tracer.convolution_initial_bins exceeds "
                    f"grid_settings.max_bins={self._grid_settings.max_bins}"
                )
            edges = np.linspace(0.0, tmax, initial_bins + 1)
        edges = np.unique(edges)
        if edges.size - 1 > self._grid_settings.max_bins:
            raise ConvolutionError(
                f"Initial tracer grid has {edges.size - 1} bins, exceeding "
                f"grid_settings.max_bins={self._grid_settings.max_bins}"
            )
        return edges

    def _prepare_tracer_grid(self) -> PreparedTracerGrid:
        """Build and cache the tracer-only adaptive grid."""
        initial_edges = self._initial_tracer_age_edges()
        if initial_edges.size == 1:
            empty = np.array([], dtype=float)
            grid = PreparedTracerGrid(
                date=self._date,
                edges=initial_edges,
                k_left=empty,
                k_mid=empty,
                k_right=empty,
            )
            self._prepared_grid = grid
            return grid

        edge_values = self._evaluate_tracer_response(initial_edges)
        right_edge_values = edge_values[1:].copy()

        # File chronicles are zero outside their declared date range. When a
        # convolution date is newer than datemax, K(age) therefore jumps at
        # age=date-datemax. That age is already a chronicle-derived bin edge,
        # but the two adjacent bins need different one-sided values there.
        boundary_dates = self._tracer.convolution_dates
        has_newest_boundary = boundary_dates is not None and np.any(
            np.asarray(boundary_dates, dtype=float) == float(self.datemax)
        )
        newest_boundary_age = float(self._date - self.datemax)
        if has_newest_boundary and 0.0 < newest_boundary_age < initial_edges[-1]:
            outside_bins = np.flatnonzero(initial_edges[1:] == newest_boundary_age)
            if outside_bins.size:
                outside_date = np.nextafter(float(self.datemax), np.inf)
                outside_age = float(self._date - outside_date)
                outside_value = float(self.get_concentration(outside_date, outside_age))
                right_edge_values[outside_bins] = outside_value

        grid = prepare_adaptive_grid(
            date=self._date,
            initial_edges=initial_edges,
            edge_values=edge_values,
            right_edge_values=right_edge_values,
            evaluate=self._evaluate_tracer_response,
            settings=self._grid_settings,
        )
        self._prepared_grid = grid
        return grid

    def _convolve_continuous(
        self,
        lpm: LPM,
        *,
        cdf_moment_provider=None,
        distribution_name: str | None = None,
    ) -> float:
        """Convolve a continuous law using its CDF and partial first moment."""
        grid = self._prepared_grid
        if grid is None or grid.date != self._date:
            grid = self._prepare_tracer_grid()
        distribution_name = distribution_name or lpm.name
        if grid.edges.size == 1:
            self._last_diagnostics = ConvolutionDiagnostics(0.0, 0, 0.0, 0)
            return 0.0

        if cdf_moment_provider is None:
            cdf_moment_provider = getattr(
                lpm,
                "cdf_and_partial_first_moment",
                None,
            )
        inherited_stub = (
            getattr(cdf_moment_provider, "__func__", None)
            is LpmBase.cdf_and_partial_first_moment
        )
        if not callable(cdf_moment_provider) or inherited_stub:
            raise ConvolutionError(
                f"Continuous LPM '{distribution_name}' must implement "
                "cdf_and_partial_first_moment()"
            )
        result, diagnostics = convolve_prepared_grid(
            grid,
            cdf_moment_provider,
            distribution_name,
            self._grid_settings,
        )
        self._last_diagnostics = diagnostics
        return result

    def window_mass(self, lpm: LPM) -> float:
        """Return probability mass in the closed available-age window.

        The window is ``[0, date - datemin]`` years. Mass outside this window
        is excluded from :meth:`convolve` and is not renormalized, so values
        below one quantify truncation by the available tracer chronicle.
        """
        tmax = max(0.0, float(self._date - self.datemin))
        strategy = lpm.convolution_strategy
        if strategy == ConvolutionStrategy.DIRAC:
            return float(0.0 <= float(lpm.get_dirac_time()) <= tmax)
        if strategy == ConvolutionStrategy.DIRAC_DOUBLE:
            first, second = lpm.get_dirac_double_time()
            rate = float(lpm.p["rate"])
            return rate * float(0.0 <= float(first) <= tmax) + (1.0 - rate) * float(
                0.0 <= float(second) <= tmax
            )
        if strategy == ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS:
            rate = float(lpm.p["rate"])
            dirac_mass = float(0.0 <= float(lpm.get_dirac_time()) <= tmax)
            values, _ = lpm.continuous_cdf_and_partial_first_moment(
                np.array([0.0, tmax])
            )
            values = np.asarray(values, dtype=float)
            if values.shape != (2,) or not np.all(np.isfinite(values)):
                raise ConvolutionError(
                    f"LPM '{lpm.name}' continuous component cannot provide "
                    "a finite window mass"
                )
            continuous_mass = float(values[1] - values[0])
            return rate * dirac_mass + (1.0 - rate) * continuous_mass
        if strategy != ConvolutionStrategy.CONTINUOUS:
            raise ConvolutionError(
                f"Unsupported convolution strategy {strategy!r} for LPM '{lpm.name}'"
            )
        values = np.asarray(lpm.cdf(np.array([0.0, tmax])), dtype=float)
        if values.shape != (2,) or not np.all(np.isfinite(values)):
            raise ConvolutionError(
                f"LPM '{lpm.name}' CDF cannot provide a finite window mass"
            )
        return float(values[1] - values[0])

    @property
    def diagnostics(self) -> ConvolutionDiagnostics | None:
        """Return diagnostics from the latest continuous or mixed convolution."""
        return self._last_diagnostics

    @property
    def prepared_grid(self) -> PreparedTracerGrid | None:
        """Return the cached tracer grid, if one has been prepared."""
        return self._prepared_grid

    @property
    def grid_settings(self) -> TracerGridSettings:
        """Return the immutable tracer-grid settings used by this instance."""
        return self._grid_settings

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
        return self._dirac_concentration(lpm.get_dirac_time())

    def _dirac_concentration(self, time: float) -> float:
        """Return a point-mass contribution only inside the tracer window."""
        age = float(time)
        tmax = float(self._date - self.datemin)
        if not np.isfinite(age) or age < 0.0 or age > tmax:
            return 0.0
        return float(self.get_concentration(self._date - age, age))

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
        convol1 = self._dirac_concentration(time1)
        convol2 = self._dirac_concentration(time2)
        return lpm.p["rate"] * convol1 + (1 - lpm.p["rate"]) * convol2

    # -------------------------------------------------------------------------
    # Mixed convolution (Dirac + normalized continuous component)
    # -------------------------------------------------------------------------

    def _convolve_mixed_dirac_continuous(self, lpm: LPM) -> float:
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
        # The model PDF represents the weighted continuous part of the full
        # mixture.  Integrate its normalized component here, then apply the
        # mixture weight exactly once below.
        continuous_part = self._convolve_continuous(
            lpm,
            cdf_moment_provider=lpm.continuous_cdf_and_partial_first_moment,
            distribution_name=f"{lpm.name} continuous component",
        )
        continuous_diagnostics = self._last_diagnostics
        if continuous_diagnostics is None:
            raise ConvolutionError("Continuous mixture diagnostics are missing")
        rate = float(lpm.p["rate"])
        tmax = float(self._date - self.datemin)
        dirac_mass = float(0.0 <= float(lpm.get_dirac_time()) <= tmax)
        self._last_diagnostics = ConvolutionDiagnostics(
            window_mass=(
                rate * dirac_mass + (1.0 - rate) * continuous_diagnostics.window_mass
            ),
            n_bins=continuous_diagnostics.n_bins,
            min_weight=(1.0 - rate) * continuous_diagnostics.min_weight,
            clipped_weight_count=continuous_diagnostics.clipped_weight_count,
        )
        return rate * dirac_part + (1.0 - rate) * continuous_part

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def prepare(self) -> PreparedTracerGrid:
        """Eagerly build and return the tracer-response grid."""
        return self._prepare_tracer_grid()

    def _convolve_once(self, lpm: LPM) -> float:
        """Dispatch one convolution according to the LPM strategy."""
        self._last_diagnostics = None
        strategy = lpm.convolution_strategy

        if strategy == ConvolutionStrategy.CONTINUOUS:
            return self._convolve_continuous(lpm)
        if strategy == ConvolutionStrategy.DIRAC:
            return self._convolution_dirac(lpm)
        if strategy == ConvolutionStrategy.DIRAC_DOUBLE:
            return self._convolution_dirac_double(lpm)
        if strategy == ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS:
            return self._convolve_mixed_dirac_continuous(lpm)
        raise ConvolutionError(
            f"Unsupported convolution strategy {strategy!r} for LPM '{lpm.name}'"
        )

    def convolve(self, lpm: LPM) -> float:
        """Compute tracer concentration at the configured observation date.

        The algorithm is automatically selected based on the LPM's
        ``convolution_strategy`` attribute. The result has the tracer's
        concentration unit. Ages and dates are decimal years, and probability
        older than ``date - datemin`` contributes zero without renormalization.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model defining the transit time distribution.
        Returns
        -------
        float
            Convolution result (tracer concentration).

        """
        return self._convolve_once(lpm)

    def convolve_date_range(
        self,
        lpm: LPM,
        date1: float,
        date2: float,
        *,
        resolution: int = 50,
    ) -> pd.DataFrame:
        """Compute convolution over a range without changing :attr:`date`.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model for convolution.
        date1 : float
            Start date (year).
        date2 : float
            End date (year).
        resolution : int
            Number of equal intervals; the returned frame has one additional
            row because both endpoints are included.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: 'date', 'concentration', 'element'.
        """
        if resolution < 1:
            raise ValueError("resolution must be at least 1")
        dates = subdivide_interval(date1, date2, resolution)
        original_date = self.date
        try:
            concentrations = []
            for sample_date in dates:
                self.date = float(sample_date)
                concentrations.append(self.convolve(lpm))
        finally:
            self.date = original_date
        return pd.DataFrame(
            {
                "date": dates,
                "concentration": concentrations,
                "element": self.name,
            }
        )


__all__ = [
    "Convolution",
    "ConvolutionDiagnostics",
    "ConvolutionError",
    "PreparedTracerGrid",
]
