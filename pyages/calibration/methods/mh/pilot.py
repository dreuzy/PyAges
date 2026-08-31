# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Pure numerical helpers for Metropolis--Hastings pilot chains.

Pilot draws are used only to learn a fixed proposal geometry for subsequent
production chains.  In particular, pooling is based on within-chain centered
draws so that differences between pilot-chain locations do not inflate the
proposal covariance.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def _positive_definite_regularization(
    covariance: np.ndarray, relative_ridge: float
) -> np.ndarray:
    """Return a symmetric positive-definite copy of one covariance matrix."""
    dimension = covariance.shape[0]
    symmetric = (covariance + covariance.T) / 2.0
    typical_variance = max(float(np.trace(symmetric) / dimension), 1.0e-12)
    regularized = symmetric + (relative_ridge * typical_variance * np.eye(dimension))

    # A zero user ridge is useful when testing a full-rank empirical covariance.
    # Add only the numerical minimum needed when the empirical matrix is singular.
    smallest_eigenvalue = float(np.linalg.eigvalsh(regularized)[0])
    if smallest_eigenvalue <= 0.0:
        numerical_ridge = max(
            np.finfo(float).eps * typical_variance,
            -smallest_eigenvalue + np.finfo(float).eps * typical_variance,
        )
        regularized = regularized + numerical_ridge * np.eye(dimension)
    return (regularized + regularized.T) / 2.0


def pooled_within_chain_covariance(
    chains: Sequence[np.ndarray], *, relative_ridge: float = 1.0e-6
) -> np.ndarray:
    """Estimate a regularized covariance from within-chain pilot variation.

    Parameters
    ----------
    chains : sequence of numpy.ndarray
        Pilot matrices shaped ``(draws, parameters)``. Every chain must contain
        at least two finite draws and use the same parameter dimension. Chain
        lengths may differ.
    relative_ridge : float, default=1e-6
        Non-negative diagonal ridge relative to the mean marginal variance.
        A minimal numerical ridge is still added when zero would leave the
        result singular.

    Returns
    -------
    numpy.ndarray
        Symmetric positive-definite pooled within-chain covariance.

    Notes
    -----
    Each chain is centered separately before its scatter matrix is accumulated.
    Consequently, differences between chain means do not enter the estimate.

    """
    if not math.isfinite(relative_ridge) or relative_ridge < 0.0:
        raise ValueError("relative_ridge must be finite and non-negative")

    arrays = tuple(np.asarray(chain, dtype=float) for chain in chains)
    if not arrays:
        raise ValueError("chains must contain at least one pilot chain")

    parameter_count: int | None = None
    scatter: np.ndarray | None = None
    degrees_of_freedom = 0
    for values in arrays:
        if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] == 0:
            raise ValueError(
                "each pilot chain must contain at least two multivariate draws"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("pilot chains must contain only finite values")
        if parameter_count is None:
            parameter_count = values.shape[1]
            scatter = np.zeros((parameter_count, parameter_count), dtype=float)
        elif values.shape[1] != parameter_count:
            raise ValueError("pilot chains must use the same parameter dimension")

        centered = values - np.mean(values, axis=0)
        scatter += centered.T @ centered
        degrees_of_freedom += values.shape[0] - 1

    if scatter is None:
        raise AssertionError("validated pilot chains must initialize the scatter")
    covariance = scatter / degrees_of_freedom
    return _positive_definite_regularization(covariance, relative_ridge)


def automatic_proposal_multiplier(dimension: int) -> float:
    """Return the conventional Gaussian random-walk scale ``2.38 / sqrt(d)``."""
    if (
        isinstance(dimension, bool)
        or not isinstance(dimension, (int, np.integer))
        or dimension <= 0
    ):
        raise ValueError("dimension must be a positive integer")
    return 2.38 / math.sqrt(int(dimension))


__all__ = ["automatic_proposal_multiplier", "pooled_within_chain_covariance"]
