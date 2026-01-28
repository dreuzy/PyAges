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
    from tracer.tracer_protocol import TracerProtocol

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


@runtime_checkable
class TracerProtocol(Protocol):
    """
    Protocol defining the interface for all tracer implementations.

    Any class implementing these properties and methods can be used
    wherever a tracer is expected, enabling polymorphism and testability.

    Properties
    ----------
    name : str
        Tracer identifier (e.g., 'cfc11', 'kr85', '3H')
    unit : str
        Concentration units (e.g., 'pptv', 'TU', 'pmC')
    datemin : float
        Minimum valid date for concentration computation
    datemax : float
        Maximum valid date for concentration computation

    Methods
    -------
    get_concentration(date, time)
        Compute concentration at given date and time
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


class SyntheticTracer:
    """
    Synthetic tracer with configurable concentration function.

    Useful for testing and for analytical studies where a specific
    concentration profile is needed without loading external data.

    Examples
    --------
        # Constant concentration
        tracer = SyntheticTracer(concentration_fn=lambda d, t: 100.0)

        # Exponential decay
        tracer = SyntheticTracer(
            name="decay_test",
            concentration_fn=lambda d, t: 100.0 * np.exp(-t / 20.0)
        )

        # Linear increase with time
        tracer = SyntheticTracer(
            concentration_fn=lambda d, t: 10.0 * t
        )
    """

    def __init__(
        self,
        name: str = "synthetic",
        unit: str = "units",
        datemin: float = 1900.0,
        datemax: float = 2100.0,
        concentration_fn=None,
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
        """
        self._name = name
        self._unit = unit
        self._datemin = datemin
        self._datemax = datemax
        self._fn = concentration_fn or (lambda d, t: 100.0 * np.exp(-np.asarray(t) / 20.0))

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
        """Compute concentration using the configured function."""
        return self._fn(date, time)


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


class DecayTracer:
    """
    Tracer with radioactive decay from constant initial concentration.

    Models tracers like 14C where the initial concentration is constant
    but decays over time.

    Concentration formula: C(t) = C0 * exp(-t / decay_time)
    """

    def __init__(
        self,
        name: str = "decay",
        unit: str = "units",
        initial_concentration: float = 100.0,
        decay_time: float = 5730.0,  # 14C half-life / ln(2)
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
        decay_time : float
            Characteristic decay time (years).
            For radioactive decay: half_life / ln(2).
        datemin : float
            Minimum valid date.
        datemax : float
            Maximum valid date.
        """
        self._name = name
        self._unit = unit
        self._c0 = initial_concentration
        self._decay_time = decay_time
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
        return self._c0 * np.exp(-np.asarray(time) / self._decay_time)
