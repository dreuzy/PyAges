# -*- coding: utf-8 -*-
"""
Tracer protocol (interface) definition.

Purpose
-------
Defines the abstract interface that all tracer implementations must follow.
This enables dependency injection and makes it possible to create synthetic
tracers for testing, or tracers with different data sources.

Usage
-----
    from pyage.tracer.tracer_protocol import TracerProtocol

    def process_tracer(tracer: TracerProtocol) -> float:
        return tracer.get_concentration(2010.0, 10.0)

    # Works with FileTracer, SyntheticTracer, or any implementation
    result = process_tracer(my_tracer)

Author
------
Jean-Raynald de Dreuzy
"""

from __future__ import annotations

from typing import Protocol, Union, runtime_checkable

import numpy as np
import numpy.typing as npt

from pyage.tracer.decay import rate_from_half_life


@runtime_checkable
class TracerProtocol(Protocol):
    """Structural interface required by the convolution engine.

    A compatible tracer supplies its identity, valid date range, convolution
    grid hints, concentration response, and basic summary values.
    """

    @property
    def name(self) -> str:
        """Tracer identifier (e.g., 'cfc11', 'kr85', '3H')."""
        ...

    @property
    def unit(self) -> str:
        """Concentration units (e.g., 'pptv', 'TU', 'pmC')."""
        ...

    @property
    def datemin(self) -> float:
        """Minimum valid date for concentration computation."""
        ...

    @property
    def datemax(self) -> float:
        """Maximum valid date for concentration computation."""
        ...

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """
        Compute concentration at given date and time.

        Parameters
        ----------
        date : float or ndarray
            Date(s) at which concentrations are computed.
            date - time = date of recharge for the input chronicle.
        time : float or ndarray
            Time(s) since recharge, used for decay and geoproduction.

        Returns
        -------
        float or ndarray
            Concentration(s) at the given date and time.
        """
        ...

    def mean_value(self, date: float) -> float:
        """Return a representative mean concentration at a reference date."""
        ...

    def max_value(self) -> float:
        """Return the maximum tracer-response value."""
        ...

    @property
    def convolution_dates(self) -> npt.NDArray[np.float64] | None:
        """Return chronicle dates used as initial convolution-grid knots."""
        ...

    @property
    def convolution_initial_bins(self) -> int:
        """Return the initial bin count when no chronicle dates are available."""
        ...


class SyntheticTracer:
    """
    Synthetic tracer with configurable concentration function.

    Useful for testing and for analytical studies where a specific
    concentration profile is needed without loading external data.

    Examples
    --------
    Create a tracer with constant concentration::

        tracer = SyntheticTracer(concentration_fn=lambda date, age: 100.0)

    The response function may also depend on age::

        tracer = SyntheticTracer(
            name="decay_test",
            concentration_fn=lambda date, age: 100.0 * np.exp(-age / 20.0),
        )
    """

    def __init__(
        self,
        name: str = "synthetic",
        unit: str = "units",
        datemin: float = 1900.0,
        datemax: float = 2100.0,
        concentration_fn=None,
        convolution_dates=None,
        convolution_initial_bins: int = 64,
    ):
        """
        Initialize a synthetic tracer.

        Parameters
        ----------
        name : str
            Tracer identifier.
        unit : str
            Concentration units.
        datemin : float
            Minimum valid date.
        datemax : float
            Maximum valid date.
        concentration_fn : callable, optional
            Function (date, time) -> concentration.
            Defaults to exponential decay: 100 * exp(-t/20).
        convolution_dates : array-like, optional
            Chronicle node dates used to seed tracer-response convolution bins.
        convolution_initial_bins : int
            Safety grid size used when no chronicle nodes are supplied. This
            protects arbitrary synthetic responses from three-point aliasing.
        """
        self._name = name
        self._unit = unit
        self._datemin = datemin
        self._datemax = datemax
        self._fn = concentration_fn or (
            lambda d, t: 100.0 * np.exp(-np.asarray(t) / 20.0)
        )
        self._convolution_dates = convolution_dates
        if int(convolution_initial_bins) < 1:
            raise ValueError("convolution_initial_bins must be at least 1")
        self._convolution_initial_bins = int(convolution_initial_bins)

    @property
    def name(self) -> str:
        """Tracer identifier."""
        return self._name

    @property
    def unit(self) -> str:
        """Concentration units."""
        return self._unit

    @property
    def datemin(self) -> float:
        """Minimum valid date."""
        return self._datemin

    @property
    def datemax(self) -> float:
        """Maximum valid date."""
        return self._datemax

    @property
    def convolution_dates(self):
        """Return source chronicle nodes when the synthetic tracer has them."""
        return self._convolution_dates

    @property
    def convolution_initial_bins(self) -> int:
        """Return the safety-grid size used when no source nodes are known."""
        return self._convolution_initial_bins

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """Compute concentration using the configured function."""
        return self._fn(date, time)

    def mean_value(self, date: float) -> float:
        """Return the zero-age response at the reference date."""
        return float(np.asarray(self.get_concentration(date, 0.0)))

    def max_value(self) -> float:
        """Estimate the maximum over the configured initial safety grid."""
        ages = np.linspace(0.0, min(100.0, self.datemax - self.datemin), 101)
        values = self.get_concentration(self.datemax - ages, ages)
        return float(np.max(np.asarray(values, dtype=float)))


class ConstantTracer:
    """
    Tracer with constant concentration (no decay, no chronicle).

    Simplest possible tracer implementation, useful for testing
    and for modeling tracers with stable atmospheric concentrations.
    """

    def __init__(
        self,
        name: str = "constant",
        unit: str = "units",
        concentration: float = 100.0,
        datemin: float = -10000.0,
        datemax: float = 2100.0,
    ):
        """
        Initialize a constant tracer.

        Parameters
        ----------
        name : str
            Tracer identifier.
        unit : str
            Concentration units.
        concentration : float
            Constant concentration value.
        datemin : float
            Minimum valid date.
        datemax : float
            Maximum valid date.
        """
        self._name = name
        self._unit = unit
        self._concentration = concentration
        self._datemin = datemin
        self._datemax = datemax

    @property
    def name(self) -> str:
        """Tracer identifier."""
        return self._name

    @property
    def unit(self) -> str:
        """Concentration units."""
        return self._unit

    @property
    def datemin(self) -> float:
        """Minimum valid date."""
        return self._datemin

    @property
    def datemax(self) -> float:
        """Maximum valid date."""
        return self._datemax

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """Return constant concentration."""
        # Return scalar or array matching input shape
        if isinstance(time, np.ndarray):
            return np.full_like(time, self._concentration, dtype=float)
        return self._concentration

    def mean_value(self, date: float) -> float:
        """Return the constant concentration."""
        return float(self._concentration)

    def max_value(self) -> float:
        """Return the constant concentration."""
        return float(self._concentration)

    @property
    def convolution_dates(self) -> None:
        """Constant tracers have no chronicle knots."""
        return None

    @property
    def convolution_initial_bins(self) -> int:
        """A single bin exactly represents a constant response."""
        return 1


class DecayTracer:
    """
    Tracer with radioactive decay from constant initial concentration.

    Models tracers like 14C where the initial concentration is constant
    but decays over time.

    Concentration formula: C(t) = C0 * exp(-ln(2) * t / half_life)
    """

    def __init__(
        self,
        name: str = "decay",
        unit: str = "units",
        initial_concentration: float = 100.0,
        half_life: float = 5730.0,
        datemin: float = -10000.0,
        datemax: float = 2100.0,
    ):
        """
        Initialize a decay tracer.

        Parameters
        ----------
        name : str
            Tracer identifier.
        unit : str
            Concentration units.
        initial_concentration : float
            Initial (recharge) concentration.
        half_life : float
            Published radioactive half-life in years.
        datemin : float
            Minimum valid date.
        datemax : float
            Maximum valid date.
        """
        self._name = name
        self._unit = unit
        self._c0 = initial_concentration
        self._decay_rate = rate_from_half_life(half_life)
        self._datemin = datemin
        self._datemax = datemax

    @property
    def name(self) -> str:
        """Tracer identifier."""
        return self._name

    @property
    def unit(self) -> str:
        """Concentration units."""
        return self._unit

    @property
    def datemin(self) -> float:
        """Minimum valid date."""
        return self._datemin

    @property
    def datemax(self) -> float:
        """Maximum valid date."""
        return self._datemax

    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
        """Compute concentration with radioactive decay."""
        return self._c0 * np.exp(-self._decay_rate * np.asarray(time))

    def mean_value(self, date: float) -> float:
        """Return the mean decayed response over the available age window."""
        ages = np.linspace(0.0, max(0.0, date - self.datemin), 1001)
        return float(np.mean(self.get_concentration(date - ages, ages)))

    def max_value(self) -> float:
        """Return the initial concentration."""
        return float(self._c0)

    @property
    def convolution_dates(self) -> None:
        """Analytical decay tracers have no chronicle knots."""
        return None

    @property
    def convolution_initial_bins(self) -> int:
        """Return the default initial grid size for a smooth decay response."""
        return 64
