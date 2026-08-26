# -*- coding: utf-8 -*-
"""
Base classes and utilities for Lumped Parameter Models (LPM).

Defines the common interface and shared numerical helpers used by
specific LPM implementations (pdf/cdf, moments, parameter handling,
and optimization utilities). Concrete models inherit from this root
to ensure consistent behavior across calibration and convolution
workflows.
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

from pyage.lpm.core.convolution_strategy import ConvolutionStrategy
from pyage.lpm.core.parameter_manager import ParameterManager


class LpmBase(abc.ABC):
    """
    Abstract base class for all Lumped Parameter Models.

    Abstract base class for all transit time distribution models used in
    groundwater age dating. Defines the common interface for probability
    distributions and parameter management.

    Class Attributes
    ----------------
    convolution_strategy : ConvolutionStrategy
        Declares which convolution algorithm should be used for this LPM type.
        Subclasses override this to indicate their requirements.
        Default is CONTINUOUS (CDF and partial-first-moment convolution).

    Instance Attributes
    -------------------
    name : str
        Name of LPM (e.g., "ig", "exp", "dirac")
    p : dict[str, float]
        Parameter values dictionary: p["parameter_name"] = value

    Abstract Methods
    ----------------
    pdf(t)
        Probability density function (must be implemented by subclasses)
    cdf(t)
        Trustworthy vectorized cumulative distribution function
    mean(), std()
        Distribution-native moments

    Virtual Methods (with default implementations)
    ----------------------------------------------
    cdf_inv(p)
        Inverse of the cumulative density function
    cdf_and_partial_first_moment(t)
        Required override for continuous convolution
    """

    # Class-level declaration of convolution strategy.
    # Subclasses override this to declare their requirements.
    # Continuous LPMs use the common CDF/partial-first-moment engine by default.
    convolution_strategy: ClassVar[ConvolutionStrategy] = ConvolutionStrategy.CONTINUOUS

    def __init__(
        self,
        name: str,
        parameter_values: dict[str, float],
        parameter_units: dict[str, str],
        directory_lpm: str,
    ) -> None:
        """
        Constructor

        Parameters
        ---------
        name: str
            LPM name
        parameter_values: dict[str, float]
            parameter_values["parameter name"] = parameter values
        parameter_units : dict[str, str]
            parameter_units["parameter name"] = parameter unit
        directory_lpm : str
            directory of the parameters necessary for the models
        """
        # Name of LPM (e.g. IG, EXP)
        self.name = name
        # Parameter Values
        self.p = parameter_values
        # Parameter Units
        self.__u = parameter_units
        if directory_lpm is None:
            raise ValueError("directory_lpm must be provided, got None")
        self._directory_lpm = directory_lpm
        # Parameter manager for bounds and loading
        self._param_manager = ParameterManager(
            model_name=name,
            directory_lpm=directory_lpm,
            parameter_names=list(parameter_values.keys()),
        )

    @abc.abstractmethod
    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """
        Probability Density Function
        Must be implemented by subclasses.

        Parameters
        ---------
        t : scalar or array
            Time values

        Returns
        -------
        pdf: scalar or array (same size as input t)
            Probability density function
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
        """
        Random uniform generation of lpm
            Modifies self with uniform random generation of parameters
            Parameters are drawn from get_param_interval()
        """
        pmin, pmax = self.get_param_interval()
        if rng is None:
            rng = np.random.default_rng()
        param = [pmin[i] + (pmax[i] - pmin[i]) * rng.random() for i in range(len(pmin))]
        self.set_param_from_array(param)

    def param_init(self) -> list[float]:
        """
        Initialization parameters in an array
            Does not change the parameters in self

        Returns
        -------
        list[float]
            Parameters in an array format
        """
        lpm_temp = copy.deepcopy(self)
        lpm_temp.load_initial_parameters()
        return lpm_temp.get_parameters_to_array()

    @property
    def lpm_data_directory(self) -> Path:
        """Return the root directory containing LPM parameter folders."""
        return Path(self._directory_lpm)

    def load_initial_parameters(self) -> None:
        """Load initial parameter values from the canonical params.yaml file."""
        self._param_manager.load_initial_values(self.p)

    def param_within_bounds(self, params: dict[str, float]) -> bool:
        """
        Test whether parameters are within the defined bounds.

        Parameters
        ----------
        params : dict[str, float]
            params to be tested, same structure as self.p

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        return self._param_manager.param_within_bounds(params)

    def param_within_bounds_array(self, params: list[float]) -> bool:
        """
        Test whether parameters are within the defined bounds.

        Parameters
        ----------
        params : list[float]
            params to be tested
            parameters should be in the same order as in the dictionary self.p

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        return self._param_manager.param_within_bounds_array(
            params, list(self.p.keys())
        )

    @abc.abstractmethod
    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Return a trustworthy, vectorized cumulative distribution function."""
        raise NotImplementedError

    def cdf_and_partial_first_moment(
        self,
        t: npt.ArrayLike,
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        """Return ``F(t)`` and ``E[T 1(T <= t)]`` for continuous convolution.

        Continuous LPMs must override this method. Discrete and mixed models
        use their dedicated convolution contracts instead.
        """
        raise NotImplementedError(
            f"Continuous LPM '{self.name}' must implement "
            "cdf_and_partial_first_moment()"
        )

    @property
    def parameter_units(self) -> dict[str, str]:
        """Return a copy of the parameter units keyed by parameter name."""
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

    def cdf_inv(self, p: float) -> float:
        """
        Inverse of the Cumulative Density Function, t = cdf^-1(p).

        The default implementation brackets the requested quantile on
        ``[0, +inf)`` and solves it with ``brentq``. Subclasses with
        analytical inverse CDFs should override this method.

        Parameters
        ---------
        p : float
            probability

        Returns
        -------
        float
            time corresponding to cdf^-1(p)
        """
        probability = float(p)
        if probability <= 0.0:
            return 0.0
        if probability >= 1.0:
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
                f"Could not bracket cdf_inv(p={probability}) for model '{self.name}' before t={upper}"
            )

        return float(
            optimize.brentq(self._cdf_minus_p, lower, upper, args=(probability,))
        )

    def set_param_from_array(self, param: list[float]) -> None:
        """Set parameters from array to dictionary."""
        for k, key in enumerate(self.p):
            self.p[key] = param[k]

    def get_parameters_to_array(self) -> list[float]:
        """Get parameters as array."""
        return list(self.p.values())

    def get_param_names(self) -> list[str]:
        """Return parameter names."""
        return list(self.p.keys())

    def get_param_range(self, param_name: str) -> float:
        """
        Gets the range of parameters.

        Parameters
        ----------
        param_name : str
            name of parameter

        Returns
        -------
        float
            Range of parameter values
        """
        return self._param_manager.get_param_range(param_name)

    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """
        Gets the interval of parameters.

        Returns
        -------
        tuple[list[float], list[float]]
            (pmin, pmax) - lower and higher bounds
        """
        return self._param_manager.get_param_interval()

    def get_p_max(self, key: str) -> float:
        """Return upper bound for parameter."""
        return self._param_manager.get_p_max(key)

    def get_p_min(self, key: str) -> float:
        """Return lower bound for parameter."""
        return self._param_manager.get_p_min(key)

    def _support_range(self) -> tuple[float, float]:
        """
        Defines Support Time Range
            Specific to the distribution itself and to its parameters

        Returns
        -------
        tuple[float, float]
            (tmin, tmax) - minimum and maximum time of support range
        """
        tmin = 0
        tmax = 1.2 * self.cdf_inv(0.98)
        return tmin, tmax

    def sample_curve(self, kind: str, count: int) -> tuple[np.ndarray, npt.ArrayLike]:
        """
        Discretization of pdf or cdf
            discretization over the model-specific support range

        Parameters
        ---------
        kind : str
            "pdf" or "cdf"
        count : int
            number of discretization steps

        Returns
        -------
        tuple[np.ndarray, array-like]
            (t, values) - discrete times and pdf/cdf values
        """
        tmin, tmax = self._support_range()
        t = np.linspace(tmin, tmax, count)
        if kind == "pdf":
            values = self.pdf(t)
        elif kind == "cdf":
            values = self.cdf(t)
        else:
            raise ValueError(f"kind must be 'pdf' or 'cdf', got {kind!r}")
        return t, values

    def load_sample(
        self,
        frame: pd.DataFrame,
        selection: str = "line",
        rng: np.random.Generator | None = None,
        row: int = 0,
    ) -> dict[str, int] | None:
        """
        Loads parameter values from distribution file

        Parameters
        ---------
        frame : pd.DataFrame
            distribution of parameter values
        selection : str
            - "random_line" : all parameters from the same random line
            - "line"        : all parameters from the specified row
        rng : np.random.Generator or None
            random number generator
        row : int
            index of the row to use if selection == "line"

        Returns
        -------
        dict[str, int] or None
            Selected row for each parameter, or ``None`` for an empty frame.
        """
        row_count = len(frame.index)
        if row_count == 0:
            return None

        if rng is None:
            rng = np.random.default_rng()

        parameter_names = list(self.p)
        if selection == "random_line":
            line = int(rng.integers(row_count))
            chosen_lines = dict.fromkeys(parameter_names, line)
        elif selection == "line":
            line = min(row, row_count - 1)
            chosen_lines = dict.fromkeys(parameter_names, line)
        else:
            raise ValueError(f"Unknown sample selection: {selection!r}")

        for key, line in chosen_lines.items():
            self.p[key] = frame[key].iloc[line]
        return chosen_lines

    def moments_name(self) -> list[str]:
        """Return moment names."""
        return ["mean", "std", "quart10", "quart25", "median", "quart75", "quart90"]

    def moments(self) -> list[float]:
        """Compute statistical characteristics of the distribution."""
        return [
            self.mean(),
            self.std(),
            self.cdf_inv(0.10),
            self.cdf_inv(0.25),
            self.cdf_inv(0.5),
            self.cdf_inv(0.75),
            self.cdf_inv(0.90),
        ]
