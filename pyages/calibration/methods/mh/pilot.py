# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file calculates the proposal covariance used by production MH chains.

"""Calculate proposal settings from preliminary Metropolis--Hastings chains.

Pilot chains are short preliminary runs. Their samples are used only to choose
the size and correlation of parameter changes proposed during the later
production chains. Pilot samples are never included in the posterior sample.

Before combining the pilot chains, this module subtracts the mean of each chain
from its own samples. A chain that happens to explore a different location
therefore does not make the proposed production steps artificially large. The
resulting covariance is regularized so that it can always be used as a
multivariate Gaussian covariance matrix.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from pyages.calibration.methods.mh.proposals import _regularize_covariance


def pooled_within_chain_covariance(
    chains: Sequence[np.ndarray], *, relative_ridge: float = 1.0e-6
) -> np.ndarray:
    """Estimate one proposal covariance from several pilot chains.

    Parameters
    ----------
    chains : sequence of numpy.ndarray
        One matrix per pilot chain, with retained draws in rows and parameters
        in columns: ``(draws, parameters)``. Every chain must contain at least
        two finite draws and the same parameters. Chain lengths may differ.
    relative_ridge : float, default=1e-6
        Size of the small value added to the covariance diagonal, expressed
        relative to the average parameter variance. This stabilizes directions
        with little or no observed variation.

    Returns
    -------
    numpy.ndarray
        A symmetric, positive-definite covariance matrix that can be passed to
        a multivariate Gaussian proposal.

    Notes
    -----
    The mean of each chain is subtracted before the chains are combined. The
    result describes how parameters vary together *inside* the chains. It does
    not treat differences between chain locations as proposal step sizes.

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
    return _regularize_covariance(covariance, relative_ridge)


def automatic_proposal_multiplier(dimension: int) -> float:
    """Return the usual proposal-size multiplier for ``dimension`` parameters.

    The value is ``2.38 / sqrt(dimension)``. It reduces joint proposal steps as
    the number of parameters increases.
    """
    if (
        isinstance(dimension, bool)
        or not isinstance(dimension, (int, np.integer))
        or dimension <= 0
    ):
        raise ValueError("dimension must be a positive integer")
    return 2.38 / math.sqrt(int(dimension))


__all__ = ["automatic_proposal_multiplier", "pooled_within_chain_covariance"]
