"""Symmetric random-walk proposals for Metropolis--Hastings calibration.

All proposals in this module are state-independent Gaussian random walks.
Consequently their Hastings log-ratio is zero.  The sum/difference proposal
uses a linear coordinate change whose inverse Jacobian has constant absolute
determinant 1/2, so that factor also cancels from every acceptance ratio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np


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
    """A fixed symmetric Gaussian random walk in native or ``(m,d)`` space."""

    covariance: np.ndarray
    coordinate_system: str = "native"

    def __post_init__(self) -> None:
        covariance = np.asarray(self.covariance, dtype=float)
        if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
            raise ValueError("proposal covariance must be a square matrix")
        if not np.all(np.isfinite(covariance)):
            raise ValueError("proposal covariance must be finite")
        if not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-12):
            raise ValueError("proposal covariance must be symmetric")
        if np.any(np.linalg.eigvalsh(covariance) <= 0.0):
            raise ValueError("proposal covariance must be positive definite")
        if self.coordinate_system not in {"native", "sum_difference"}:
            raise ValueError("coordinate_system must be 'native' or 'sum_difference'")
        if self.coordinate_system == "sum_difference" and covariance.shape != (2, 2):
            raise ValueError("sum/difference proposals require a 2x2 covariance")
        object.__setattr__(self, "covariance", covariance.copy())

    @classmethod
    def diagonal(
        cls, scales: Sequence[float], coordinate_system: str = "native"
    ) -> "GaussianRandomWalk":
        values = np.asarray(scales, dtype=float)
        if values.ndim != 1 or np.any(values <= 0.0) or not np.all(np.isfinite(values)):
            raise ValueError("proposal scales must be finite positive values")
        return cls(np.diag(values**2), coordinate_system=coordinate_system)

    def draw(self, current: Sequence[float], rng: np.random.Generator) -> np.ndarray:
        """Draw one proposal; physical bounds are checked by the target."""
        state = np.asarray(current, dtype=float)
        if state.shape != (self.covariance.shape[0],):
            raise ValueError("current state and proposal covariance dimensions differ")
        if self.coordinate_system == "sum_difference":
            transformed = native_to_sum_difference(state)
            proposed = transformed + rng.multivariate_normal(
                np.zeros(len(state)), self.covariance
            )
            return sum_difference_to_native(proposed)
        return state + rng.multivariate_normal(np.zeros(len(state)), self.covariance)

    @staticmethod
    def log_hastings_ratio(
        current: Sequence[float], proposed: Sequence[float]
    ) -> float:
        """Fixed Gaussian random walks are symmetric in either coordinate system."""
        del current, proposed
        return 0.0


__all__ = [
    "GaussianRandomWalk",
    "native_to_sum_difference",
    "regularize_empirical_covariance",
    "sum_difference_inverse_jacobian",
    "sum_difference_log_abs_det_jacobian",
    "sum_difference_to_native",
]
