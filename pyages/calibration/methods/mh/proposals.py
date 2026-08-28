# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Fixed random-walk proposals for Metropolis--Hastings calibration.

Native-space proposals are symmetric. The sum/difference proposal uses a
linear coordinate change whose constant Jacobian cancels. A proposal in
SciPy's inverse-Gaussian ``(shape, scale, shift)`` coordinates has a
state-dependent Jacobian and therefore supplies its exact Hastings correction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np

from pyages.calibration.methods.mh.ig_coordinates import (
    physical_to_scipy_coordinates,
    scipy_to_physical_coordinates,
)


class Proposal(Protocol):
    """Common interface used by every Metropolis--Hastings proposal."""

    def draw(self, current: Sequence[float], rng: np.random.Generator) -> np.ndarray:
        """Draw one proposal in native LPM parameter order."""

    def log_hastings_ratio(
        self, current: Sequence[float], proposed: Sequence[float]
    ) -> float:
        """Return ``log q(current|proposed) - log q(proposed|current)``."""


class ComponentwiseRandomWalk:
    """Independent scalar Gaussian steps in native LPM coordinates.

    Scalar calls to ``standard_normal`` deliberately preserve the historical
    seeded protocol independently of NumPy's multivariate implementation.
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
            values = [self.fraction * lpm.get_param_range(name) for name in self.names]
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


def regularize_empirical_covariance(
    samples: np.ndarray, relative_ridge: float = 1.0e-6
) -> np.ndarray:
    """Estimate a covariance and add a small scale-aware diagonal ridge."""
    values = np.asarray(samples, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("samples must contain at least two multivariate draws")
    if relative_ridge < 0.0 or not math.isfinite(relative_ridge):
        raise ValueError("relative_ridge must be finite and non-negative")
    covariance = np.atleast_2d(np.cov(values, rowvar=False, ddof=1))
    typical_variance = max(float(np.trace(covariance) / covariance.shape[0]), 1.0e-12)
    return covariance + relative_ridge * typical_variance * np.eye(covariance.shape[0])


@dataclass(frozen=True)
class GaussianRandomWalk:
    r"""Fixed Gaussian random walk in a declared coordinate system.

    ``covariance`` is expressed in squared units of ``coordinate_system`` and
    is held constant throughout the chain; no adaptation occurs. Native and
    linear sum/difference proposals are symmetric in physical parameters. For
    ``scipy_ig``, the Gaussian is symmetric in SciPy
    ``(shape, scale, shift)`` coordinates, but transformation to physical
    ``(M, S, shift)`` coordinates makes the proposal asymmetric.

    Since ``|d(shape, scale)/d(M, S)| = 2/S``, the SciPy-IG Hastings term is
    ``log(S_proposed / S_current)``. Physical LPM bounds are checked by the
    target after drawing; this class does not truncate or reflect proposals.
    """

    covariance: np.ndarray
    coordinate_system: str = "native"

    def __post_init__(self) -> None:
        """Validate and copy the fixed proposal covariance."""
        covariance = np.asarray(self.covariance, dtype=float)
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
        object.__setattr__(self, "covariance", covariance.copy())

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
        """Draw one unbounded proposal in the declared coordinate system."""
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
        r"""Return ``log q(current|proposed) - log q(proposed|current)``.

        The value is zero for native and sum/difference coordinates. For
        ``scipy_ig`` it is ``log(S_proposed / S_current)`` from the nonlinear
        inverse-Gaussian coordinate Jacobian.
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
            # |d(shape,scale)/d(M,S)|=2/S.
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
