# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Define common contracts and numerical helpers for LPM implementations.

Summary
-------
1. ``LpmBase`` is the abstract root of every transit-time distribution model.
2. Construction validates finite parameters, matching units, and YAML metadata.
3. Subclasses provide vectorized PDF, CDF, mean, and standard-deviation methods.
4. Continuous models also expose cumulative mass and partial first moments.
5. Parameter dictionary order is the canonical calibration-vector order.
6. ``ParameterManager`` supplies initial values, bounds, and parameter ranges.
7. The base inverse CDF validates probabilities and brackets scalar quantiles.
8. Plot sampling evaluates a PDF or CDF on a compact quantile-based age window.
9. Data-frame loading validates a complete row before changing model parameters.
10. Moment helpers expose the mean, spread, and five consistently named quantiles.

Reading order
-------------
Start with :class:`LpmBase` and its constructor contract. Then read the abstract
distribution methods and continuous-convolution contract. Continue with the
parameter-management methods, then the CDF inversion helpers. Finish with
plot/sample loading and the moment helpers at the end of the class.
"""

from __future__ import annotations

import abc
import copy
from pathlib import Path
from typing import ClassVar

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import optimize

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.parameter_manager import ParameterManager


class LpmBase(abc.ABC):
    """Define the common interface for groundwater transit-time models.

    An LPM represents a probability distribution of non-negative transit
    times. Concrete subclasses provide the probability density, cumulative
    distribution, mean, and standard deviation. Continuous models must also
    provide the cumulative mass and raw partial first moment used by the
    continuous convolution engine.

    Parameters
    ----------
    name : str
        Registered model identifier. It must match the model directory and
        the ``model`` represented by ``params.yaml``.
    parameter_values : dict[str, float]
        Current model parameters. Dictionary insertion order defines the
        canonical array order used by calibration methods.
    parameter_units : dict[str, str]
        Physical unit associated with each model parameter.
    directory_lpm : str or pathlib.Path
        Root directory containing ``<name>/params.yaml``.

    Attributes
    ----------
    name : str
        Registered model identifier.
    p : dict[str, float]
        Mutable parameter values in canonical calibration order.
    convolution_strategy : ConvolutionStrategy
        Algorithm used to convolve this distribution with a tracer response.

    Raises
    ------
    ValueError
        If the directory or parameter metadata is invalid.
    FileNotFoundError
        If the model parameter file cannot be found.
    """

    # New continuous models get the common CDF/partial-moment engine by default.
    convolution_strategy: ClassVar[ConvolutionStrategy] = ConvolutionStrategy.CONTINUOUS

    def __init__(
        self,
        name: str,
        parameter_values: dict[str, float],
        parameter_units: dict[str, str],
        directory_lpm: str | Path,
    ) -> None:
        """Initialize shared LPM state and validate parameter metadata."""
        if directory_lpm is None:
            raise ValueError("directory_lpm must be provided, got None")

        parameter_names = list(parameter_values)
        if set(parameter_units) != set(parameter_names):
            missing = sorted(set(parameter_names) - set(parameter_units))
            extra = sorted(set(parameter_units) - set(parameter_names))
            raise ValueError(
                "parameter_units must match parameter_values "
                f"(missing={missing}, extra={extra})"
            )
        try:
            finite_parameters = all(
                np.isfinite(float(value)) for value in parameter_values.values()
            )
        except (TypeError, ValueError):
            finite_parameters = False
        if not finite_parameters:
            raise ValueError("LPM parameters must be finite numeric values")

        self.name = name
        # Dictionary order is the canonical parameter-vector order.
        self.p = dict(parameter_values)
        self.__u = dict(parameter_units)
        self._directory_lpm = Path(directory_lpm)
        self._param_manager = ParameterManager(
            model_name=name,
            directory_lpm=self._directory_lpm,
            parameter_names=parameter_names,
        )

    @abc.abstractmethod
    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the probability density at one or more transit times.

        Parameters
        ----------
        t : array-like
            Scalar or array of transit times in years.

        Returns
        -------
        float or numpy.ndarray
            Density values with the same shape as ``t``.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def mean(self) -> float:
        """Return the exact or distribution-native mean."""
        raise NotImplementedError

    @abc.abstractmethod
    def std(self) -> float:
        """Return the exact or distribution-native standard deviation."""
        raise NotImplementedError

    def random_uniform(self, rng: np.random.Generator | None = None) -> None:
        """Replace all parameters with independent uniform draws within bounds.

        Parameters
        ----------
        rng : numpy.random.Generator, optional
            Random generator. A new default generator is created when omitted.

        Notes
        -----
        This method mutates :attr:`p`.
        """
        pmin, pmax = self.get_param_interval()
        if rng is None:
            rng = np.random.default_rng()
        param = [pmin[i] + (pmax[i] - pmin[i]) * rng.random() for i in range(len(pmin))]
        self.set_param_from_array(param)

    def param_init(self) -> list[float]:
        """Return YAML initial values in canonical parameter order.

        Returns
        -------
        list[float]
            Initial parameter values ordered like :attr:`p`.

        Notes
        -----
        The current model is not modified.
        """
        lpm_temp = copy.deepcopy(self)
        lpm_temp.load_initial_parameters()
        return lpm_temp.get_parameters_to_array()

    @property
    def lpm_data_directory(self) -> Path:
        """Return the root directory containing LPM parameter folders."""
        return self._directory_lpm

    def load_initial_parameters(self) -> None:
        """Replace current parameters with initial values from ``params.yaml``."""
        self._param_manager.load_initial_values(self.p)

    def param_within_bounds(self, params: dict[str, float]) -> bool:
        """Return whether a complete parameter mapping is finite and in bounds.

        Parameters
        ----------
        params : dict[str, float]
            Candidate values. Keys must exactly match :attr:`p`.

        Returns
        -------
        bool
            ``True`` only when names and values satisfy the complete contract.
        """
        return self._param_manager.param_within_bounds(params)

    def param_within_bounds_array(self, params: npt.ArrayLike) -> bool:
        """Return whether an ordered parameter vector is finite and in bounds.

        Parameters
        ----------
        params : array-like
            One-dimensional candidate values in the order of :attr:`p`.

        Returns
        -------
        bool
            ``True`` only for a correctly sized, finite vector in bounds.
        """
        try:
            values = np.asarray(params, dtype=float)
        except (TypeError, ValueError):
            return False
        if values.shape != (len(self.p),) or not np.all(np.isfinite(values)):
            return False
        return self._param_manager.param_within_bounds_array(
            values.tolist(), list(self.p)
        )

    @abc.abstractmethod
    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the cumulative distribution at one or more transit times."""
        raise NotImplementedError

    def cdf_and_partial_first_moment(
        self,
        t: npt.ArrayLike,
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        r"""Evaluate cumulative mass and the raw partial first moment.

        For every age :math:`t`, this method returns

        .. math::

           F(t) = P(T \leq t)

        and

        .. math::

           M_1(t) = E[T\,1(T \leq t)].

        The continuous convolution engine uses both quantities to integrate a
        piecewise-linear tracer response without reconstructing the PDF.

        Parameters
        ----------
        t : array-like
            Scalar or array of transit times in years.

        Returns
        -------
        cdf : float or numpy.ndarray
            Cumulative probabilities with the same shape as ``t``.
        partial_first_moment : float or numpy.ndarray
            Raw partial first moments with the same shape as ``t``.

        Raises
        ------
        NotImplementedError
            If a continuous subclass does not implement this contract.

        Notes
        -----
        Implementations must be vectorized and consistent with :meth:`cdf`.
        Discrete and mixed models use their dedicated convolution contracts.
        """
        raise NotImplementedError(
            f"Continuous LPM '{self.name}' must implement "
            "cdf_and_partial_first_moment()"
        )

    @property
    def parameter_units(self) -> dict[str, str]:
        """Return a defensive copy of units keyed by parameter name."""
        return dict(self.__u)

    def _cdf_minus_p(self, t: float, p: float) -> float:
        """Instrumental function for cdf_inv."""
        return self._cdf_scalar(t) - p

    def _cdf_scalar(self, t: float) -> float:
        """Evaluate the CDF at a scalar time value."""
        cdf_val = np.asarray(self.cdf(np.array([t], dtype=float)), dtype=float)
        if cdf_val.size != 1:
            raise ValueError(
                f"Expected scalar-compatible CDF output, got shape {cdf_val.shape}"
            )
        return float(cdf_val.reshape(-1)[0])

    @staticmethod
    def _validated_probabilities(p: npt.ArrayLike) -> np.ndarray:
        """Return finite probabilities after validating the closed unit interval."""
        try:
            probabilities = np.asarray(p, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Probabilities must be numeric, got {p!r}") from exc
        if np.any(~np.isfinite(probabilities)) or np.any(
            (probabilities < 0.0) | (probabilities > 1.0)
        ):
            raise ValueError(f"Probabilities must be finite and in [0, 1], got {p!r}")
        return probabilities

    def cdf_inv(self, p: float) -> float:
        """Evaluate a scalar quantile by numerically inverting the CDF.

        The default implementation brackets the requested quantile on
        ``[0, 1e9]`` years and solves it with ``scipy.optimize.brentq``.
        Subclasses with analytical inverse CDFs should override this method.

        Parameters
        ----------
        p : float
            Finite probability in the half-open interval ``[0, 1)``.

        Returns
        -------
        float
            Transit-time quantile in years.

        Raises
        ------
        ValueError
            If ``p`` is not scalar, finite, or in ``[0, 1)``.
        RuntimeError
            If the requested quantile cannot be bracketed before ``1e9`` years.
        """
        probabilities = self._validated_probabilities(p)
        if probabilities.ndim != 0:
            raise ValueError("The base cdf_inv implementation expects a scalar")
        probability = float(probabilities)
        if probability == 0.0:
            return 0.0
        if probability == 1.0:
            raise ValueError(f"cdf_inv expects 0 <= p < 1, got {probability}")

        lower = 0.0
        f_lower = self._cdf_minus_p(lower, probability)
        if f_lower >= 0.0:
            return lower

        upper = 10.0
        max_upper = 1.0e9
        f_upper = self._cdf_minus_p(upper, probability)
        while f_upper < 0.0 and upper < max_upper:
            upper *= 2.0
            f_upper = self._cdf_minus_p(upper, probability)

        if not np.isfinite(f_upper) or f_upper < 0.0:
            raise RuntimeError(
                f"Could not bracket cdf_inv(p={probability}) for model "
                f"'{self.name}' before t={upper}"
            )

        return float(
            optimize.brentq(self._cdf_minus_p, lower, upper, args=(probability,))
        )

    def set_param_from_array(self, param: npt.ArrayLike) -> None:
        """Atomically replace all parameters from an ordered one-dimensional array.

        Parameters
        ----------
        param : array-like
            Finite values in the canonical order defined by :attr:`p`.

        Raises
        ------
        ValueError
            If the values are non-finite or do not form a vector of the exact
            expected length.

        Notes
        -----
        Validation completes before :attr:`p` is mutated.
        """
        try:
            values = np.asarray(param, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError("LPM parameters must be numeric") from exc
        expected_shape = (len(self.p),)
        if values.shape != expected_shape:
            raise ValueError(
                f"Expected parameter shape {expected_shape}, got {values.shape}"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("LPM parameters must be finite")

        self.p.update(zip(self.p, values.tolist(), strict=True))

    def get_parameters_to_array(self) -> list[float]:
        """Return parameter values in canonical calibration order."""
        return list(self.p.values())

    def get_param_names(self) -> list[str]:
        """Return parameter names in canonical calibration order."""
        return list(self.p.keys())

    def get_param_range(self, param_name: str) -> float:
        """Return the configured range of one parameter.

        Parameters
        ----------
        param_name : str
            Parameter name.

        Returns
        -------
        float
            Upper bound minus lower bound.
        """
        return self._param_manager.get_param_range(param_name)

    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """Return lower and upper bounds in canonical parameter order.

        Returns
        -------
        tuple[list[float], list[float]]
            Lists of lower and upper bounds, respectively.
        """
        return self._param_manager.get_param_interval()

    def get_p_max(self, key: str) -> float:
        """Return upper bound for parameter."""
        return self._param_manager.get_p_max(key)

    def get_p_min(self, key: str) -> float:
        """Return lower bound for parameter."""
        return self._param_manager.get_p_min(key)

    def _plot_range(self) -> tuple[float, float]:
        """Return an approximate age window intended only for visualization."""
        # Extending Q(0.98) keeps plots compact while showing most of the tail.
        return 0.0, 1.2 * float(self.cdf_inv(0.98))

    def sample_curve(self, kind: str, count: int) -> tuple[np.ndarray, npt.ArrayLike]:
        """Sample the PDF or CDF over a model-specific plotting window.

        Parameters
        ----------
        kind : str
            Quantity to evaluate: ``"pdf"`` or ``"cdf"``.
        count : int
            Number of sample points; must be at least two.

        Returns
        -------
        times : numpy.ndarray
            Evenly spaced transit times.
        values : array-like
            PDF or CDF evaluated at ``times``.

        Raises
        ------
        ValueError
            If ``kind`` is unknown or ``count`` is not an integer of at least
            two.

        Notes
        -----
        The plotting window is not the complete mathematical support.
        """
        if kind not in {"pdf", "cdf"}:
            raise ValueError(f"kind must be 'pdf' or 'cdf', got {kind!r}")
        if (
            isinstance(count, (bool, np.bool_))
            or not isinstance(count, (int, np.integer))
            or count < 2
        ):
            raise ValueError(f"count must be an integer >= 2, got {count!r}")

        tmin, tmax = self._plot_range()
        t = np.linspace(tmin, tmax, count)
        if kind == "pdf":
            values = self.pdf(t)
        else:
            values = self.cdf(t)
        return t, values

    def load_sample(
        self,
        frame: pd.DataFrame,
        selection: str = "line",
        rng: np.random.Generator | None = None,
        row: int = 0,
    ) -> int | None:
        """Atomically load one parameter row from a data frame.

        Parameters
        ----------
        frame : pd.DataFrame
            Candidate parameter rows. It must contain every parameter column.
        selection : str
            ``"random_line"`` selects one random row; ``"line"`` uses ``row``.
        rng : np.random.Generator or None
            Generator used by ``"random_line"``.
        row : int
            Zero-based positional row used by ``"line"``.

        Returns
        -------
        int or None
            Zero-based position of the selected row, or ``None`` for an empty
            frame.

        Raises
        ------
        KeyError
            If a required parameter column is missing.
        IndexError
            If ``row`` is outside the data frame.
        ValueError
            If the selection mode or selected values are invalid.

        Notes
        -----
        Validation completes before :attr:`p` is mutated.
        """
        row_count = len(frame.index)
        if row_count == 0:
            return None

        parameter_names = list(self.p)
        missing_columns = [name for name in parameter_names if name not in frame]
        if missing_columns:
            raise KeyError(f"Missing parameter columns: {missing_columns}")

        if selection == "random_line":
            if rng is None:
                rng = np.random.default_rng()
            line = int(rng.integers(row_count))
        elif selection == "line":
            if (
                isinstance(row, (bool, np.bool_))
                or not isinstance(row, (int, np.integer))
                or not 0 <= row < row_count
            ):
                raise IndexError(f"row must be in [0, {row_count - 1}], got {row!r}")
            line = int(row)
        else:
            raise ValueError(f"Unknown sample selection: {selection!r}")

        selected_values = [frame[key].iloc[line] for key in parameter_names]
        self.set_param_from_array(selected_values)
        return line

    def moments_name(self) -> list[str]:
        """Return labels corresponding positionally to :meth:`moments`."""
        return ["mean", "std", "p10", "p25", "p50", "p75", "p90"]

    def moments(self) -> list[float]:
        """Return mean, standard deviation, and selected quantiles."""
        return [
            self.mean(),
            self.std(),
            self.cdf_inv(0.10),
            self.cdf_inv(0.25),
            self.cdf_inv(0.5),
            self.cdf_inv(0.75),
            self.cdf_inv(0.90),
        ]
