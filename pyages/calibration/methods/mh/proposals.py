# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines how an MH chain proposes its next parameter values.

"""Create candidate parameter values for each Metropolis--Hastings step.

The sampler can change each parameter separately or draw all changes together
from a multivariate Gaussian distribution. The Gaussian covariance is fixed
before a production chain starts; this module does not adapt it while sampling.

Most proposal modes are symmetric: proposing B from A has the same density as
proposing A from B, so their Hastings correction is zero. The inverse-Gaussian
mode draws in SciPy's ``(shape, scale, shift)`` parameter system and converts
back to physical ``(mean, standard deviation, shift)`` values. That nonlinear
conversion is not symmetric in physical coordinates, so this module also
calculates the correction required by the acceptance probability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np

from pyages.calibration.methods.mh._immutable import immutable_float_array
from pyages.calibration.methods.mh.ig_coordinates import (
    physical_to_scipy_coordinates,
    scipy_to_physical_coordinates,
)


class Proposal(Protocol):
    """Operations that every proposal mechanism must provide to the sampler."""

    def draw(self, current: Sequence[float], rng: np.random.Generator) -> np.ndarray:
        """Return candidate parameters in the model's parameter order."""

    def log_hastings_ratio(
        self, current: Sequence[float], proposed: Sequence[float]
    ) -> float:
        """Return the correction for unequal forward and reverse probabilities."""


class ComponentwiseRandomWalk:
    """Propose a separate Gaussian change for every model parameter.

    Each parameter has its own fixed step size. The class draws the random
    changes one at a time to preserve the historical results produced by a
    given seed, independently of NumPy's multivariate Gaussian implementation.
    """

    def __init__(self, source: str, fraction: float) -> None:
        """Store the step source and scale until an LPM is prepared."""
        self.source = source
        self.fraction = fraction
        self.names: tuple[str, ...] = ()
        self.steps: np.ndarray | None = None

    def prepare(self, lpm: Any) -> None:
        """Resolve ordered finite positive steps for a concrete LPM."""
        self.names = tuple(lpm.p)
        if self.source == "bounds":
            values = [
                self.fraction * lpm.get_calibration_range_width(name)
                for name in self.names
            ]
        else:
            from pyages.data_io import lpm_params

            schema = lpm_params.load_parameter_schema(
                lpm.name,
                lpm.lpm_data_directory,
            )
            configured = lpm_params.get_steps(schema)
            missing = [name for name in self.names if name not in configured]
            extra = [name for name in configured if name not in lpm.p]
            if missing or extra:
                raise ValueError(
                    "Configured MH steps must match the LPM parameters "
                    f"(missing={missing}, extra={extra})"
                )
            values = [configured[name] for name in self.names]
        steps = np.asarray(values, dtype=float)
        if np.any(steps <= 0.0) or not np.all(np.isfinite(steps)):
            raise ValueError("Configured MH steps must be finite and positive")
        self.steps = steps

    def draw(self, current: Sequence[float], rng: np.random.Generator) -> np.ndarray:
        """Draw one scalar increment per native parameter."""
        if self.steps is None:
            raise RuntimeError("prepare(lpm) must be called before drawing")
        state = np.asarray(current, dtype=float)
        if state.shape != self.steps.shape:
            raise ValueError("current state and componentwise steps dimensions differ")
        increments = np.asarray(
            [step * rng.standard_normal() for step in self.steps],
            dtype=float,
        )
        return state + increments

    def log_hastings_ratio(
        self, current: Sequence[float], proposed: Sequence[float]
    ) -> float:
        """Return zero because the native Gaussian increments are symmetric."""
        return 0.0

    def add_metadata(self, data: dict[str, Any]) -> None:
        """Append resolved componentwise settings to run metadata."""
        if self.steps is None:
            return
        data["MH_delta_source"] = self.source
        if self.source == "bounds":
            data["MH_delta_fraction"] = self.fraction
        for name, value in zip(self.names, self.steps, strict=True):
            data[f"MH_delta_{name}"] = float(value)


def native_to_sum_difference(theta: Sequence[float]) -> np.ndarray:
    """Return ``(m, d) = (mu + t0, mu - t0)``."""
    values = np.asarray(theta, dtype=float)
    if values.shape != (2,):
        raise ValueError("sum/difference coordinates require exactly two parameters")
    mu, t0 = values
    return np.array([mu + t0, mu - t0], dtype=float)


def sum_difference_to_native(coordinates: Sequence[float]) -> np.ndarray:
    """Return ``(mu, t0) = ((m + d)/2, (m - d)/2)``."""
    values = np.asarray(coordinates, dtype=float)
    if values.shape != (2,):
        raise ValueError("sum/difference coordinates require exactly two parameters")
    m, d = values
    return np.array([(m + d) / 2.0, (m - d) / 2.0], dtype=float)


def sum_difference_inverse_jacobian() -> np.ndarray:
    """Jacobian of ``(m, d) -> (mu, t0)`` (constant everywhere)."""
    return np.array([[0.5, 0.5], [0.5, -0.5]], dtype=float)


def sum_difference_log_abs_det_jacobian() -> float:
    """Return log ``|d(mu,t0)/d(m,d)| = log(1/2)``."""
    return -math.log(2.0)


def _regularize_covariance(
    covariance: np.ndarray,
    relative_ridge: float,
) -> np.ndarray:
    """Return one finite symmetric positive-definite covariance matrix."""
    values = np.asarray(covariance, dtype=float)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[0] != values.shape[1]:
        raise ValueError("covariance must be a non-empty square matrix")
    if not np.all(np.isfinite(values)):
        raise ValueError("covariance must contain only finite values")
    if relative_ridge < 0.0 or not math.isfinite(relative_ridge):
        raise ValueError("relative_ridge must be finite and non-negative")

    symmetric = (values + values.T) / 2.0
    dimension = symmetric.shape[0]
    typical_variance = max(float(np.trace(symmetric) / dimension), 1.0e-12)
    regularized = symmetric + (relative_ridge * typical_variance * np.eye(dimension))
    smallest_eigenvalue = float(np.linalg.eigvalsh(regularized)[0])
    if smallest_eigenvalue <= 0.0:
        numerical_ridge = max(
            np.finfo(float).eps * typical_variance,
            -smallest_eigenvalue + np.finfo(float).eps * typical_variance,
        )
        regularized = regularized + numerical_ridge * np.eye(dimension)
    return (regularized + regularized.T) / 2.0


def regularize_empirical_covariance(
    samples: np.ndarray, relative_ridge: float = 1.0e-6
) -> np.ndarray:
    """Estimate covariance and stabilize parameter directions with low variance.

    The added diagonal value is scaled to the average variance, so the same
    ``relative_ridge`` remains meaningful when parameter units change.
    """
    values = np.asarray(samples, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("samples must contain at least two multivariate draws")
    covariance = np.atleast_2d(np.cov(values, rowvar=False, ddof=1))
    return _regularize_covariance(covariance, relative_ridge)


@dataclass(frozen=True)
class GaussianRandomWalk:
    r"""Propose all parameter changes together with one fixed Gaussian model.

    ``covariance`` controls both the size of each parameter change and how the
    changes are correlated. It is expressed in the selected coordinate system
    and does not change while the chain runs.

    In ``native`` mode, the Gaussian is applied directly to the model
    parameters. In ``sum_difference`` mode, two parameters are temporarily
    replaced by their sum and difference. Both modes have equal forward and
    reverse proposal probabilities.

    In ``scipy_ig`` mode, the Gaussian is applied to SciPy's inverse-Gaussian
    ``(shape, scale, shift)`` values and the result is converted back to
    physical ``(M, S, shift)`` values. This nonlinear conversion makes the
    forward and reverse probabilities unequal.

    The required correction is ``log(S_proposed / S_current)`` because
    ``|d(shape, scale)/d(M, S)| = 2/S``. This class may propose values outside
    the configured calibration ranges; the target evaluation rejects them later.
    """

    covariance: np.ndarray
    coordinate_system: str = "native"

    def __post_init__(self) -> None:
        """Validate and copy the fixed proposal covariance."""
        covariance = np.array(self.covariance, dtype=float, copy=True)
        if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
            raise ValueError("proposal covariance must be a square matrix")
        if not np.all(np.isfinite(covariance)):
            raise ValueError("proposal covariance must be finite")
        if not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-12):
            raise ValueError("proposal covariance must be symmetric")
        if np.any(np.linalg.eigvalsh(covariance) <= 0.0):
            raise ValueError("proposal covariance must be positive definite")
        if self.coordinate_system not in {"native", "sum_difference", "scipy_ig"}:
            raise ValueError(
                "coordinate_system must be 'native', 'sum_difference' or 'scipy_ig'"
            )
        if self.coordinate_system == "sum_difference" and covariance.shape != (2, 2):
            raise ValueError("sum/difference proposals require a 2x2 covariance")
        if self.coordinate_system == "scipy_ig" and covariance.shape != (3, 3):
            raise ValueError("SciPy IG proposals require a 3x3 covariance")
        object.__setattr__(self, "covariance", immutable_float_array(covariance))

    def __deepcopy__(self, _memo: dict[int, object]) -> "GaussianRandomWalk":
        """Return self because the proposal contains only immutable values."""
        return self

    def __reduce__(self) -> tuple[object, tuple[np.ndarray, str]]:
        """Rebuild through validation so unpickled covariance stays immutable."""
        return type(self), (self.covariance, self.coordinate_system)

    @classmethod
    def diagonal(
        cls, scales: Sequence[float], coordinate_system: str = "native"
    ) -> "GaussianRandomWalk":
        """Build a diagonal covariance from coordinate standard deviations."""
        values = np.asarray(scales, dtype=float)
        if values.ndim != 1 or np.any(values <= 0.0) or not np.all(np.isfinite(values)):
            raise ValueError("proposal scales must be finite positive values")
        return cls(np.diag(values**2), coordinate_system=coordinate_system)

    def draw(self, current: Sequence[float], rng: np.random.Generator) -> np.ndarray:
        """Draw a candidate without clipping it to calibration ranges."""
        state = np.asarray(current, dtype=float)
        if state.shape != (self.covariance.shape[0],):
            raise ValueError("current state and proposal covariance dimensions differ")
        if self.coordinate_system == "sum_difference":
            transformed = native_to_sum_difference(state)
            proposed = transformed + rng.multivariate_normal(
                np.zeros(len(state)), self.covariance
            )
            return sum_difference_to_native(proposed)
        if self.coordinate_system == "scipy_ig":
            transformed = physical_to_scipy_coordinates(state)
            proposed = transformed + rng.multivariate_normal(
                np.zeros(len(state)), self.covariance
            )
            return scipy_to_physical_coordinates(proposed)
        return state + rng.multivariate_normal(np.zeros(len(state)), self.covariance)

    def log_hastings_ratio(
        self, current: Sequence[float], proposed: Sequence[float]
    ) -> float:
        r"""Return the correction for forward and reverse proposal probabilities.

        Native and sum/difference proposals are symmetric, so their correction
        is zero. The nonlinear ``scipy_ig`` conversion requires
        ``log(S_proposed / S_current)``.
        """
        if self.coordinate_system == "scipy_ig":
            current_values = np.asarray(current, dtype=float)
            proposed_values = np.asarray(proposed, dtype=float)
            if (
                current_values.shape != (3,)
                or proposed_values.shape != (3,)
                or current_values[1] <= 0.0
                or proposed_values[1] <= 0.0
                or not np.all(np.isfinite(proposed_values))
            ):
                return 0.0
            # Changing from (M, S) to (shape, scale) multiplies density by 2/S.
            # The constants cancel between directions, leaving S_new / S_old.
            return math.log(proposed_values[1] / current_values[1])
        return 0.0


__all__ = [
    "ComponentwiseRandomWalk",
    "GaussianRandomWalk",
    "Proposal",
    "native_to_sum_difference",
    "regularize_empirical_covariance",
    "sum_difference_inverse_jacobian",
    "sum_difference_log_abs_det_jacobian",
    "sum_difference_to_native",
]
