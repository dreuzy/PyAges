# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""In-memory tracer implementations for tests and analytical studies."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from pyages.tracer.decay import rate_from_half_life


class SyntheticTracer:
    """Synthetic tracer with a configurable concentration function.

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
        """Initialize a synthetic tracer.

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
            Function ``(date, time) -> concentration``. Defaults to the
            exponential response ``100 * exp(-time / 20)``.
        convolution_dates : array-like, optional
            Chronicle node dates used to seed tracer-response convolution bins.
        convolution_initial_bins : int
            Safety grid size used when no chronicle nodes are supplied.
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
        date: float | npt.NDArray[np.float64],
        time: float | npt.NDArray[np.float64],
    ) -> float | npt.NDArray[np.float64]:
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
    """Tracer with constant concentration, no decay, and no chronicle."""

    def __init__(
        self,
        name: str = "constant",
        unit: str = "units",
        concentration: float = 100.0,
        datemin: float = -10000.0,
        datemax: float = 2100.0,
    ):
        """Initialize a constant tracer."""
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
        date: float | npt.NDArray[np.float64],
        time: float | npt.NDArray[np.float64],
    ) -> float | npt.NDArray[np.float64]:
        """Return constant concentration."""
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
    """Tracer with radioactive decay from a constant initial concentration.

    The response follows ``C(time) = C0 * exp(-ln(2) * time / half_life)``.
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
        """Initialize a radioactive-decay tracer."""
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
        date: float | npt.NDArray[np.float64],
        time: float | npt.NDArray[np.float64],
    ) -> float | npt.NDArray[np.float64]:
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


__all__ = ["ConstantTracer", "DecayTracer", "SyntheticTracer"]
