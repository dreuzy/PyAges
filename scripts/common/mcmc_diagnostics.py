# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Dependency-light rank-normalized diagnostics for multi-chain MCMC output."""

from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata


def split_chains(values: np.ndarray) -> np.ndarray:
    """Split each chain into equal first and last halves."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 4:
        raise ValueError("values must contain at least two chains and four draws")
    half = values.shape[1] // 2
    return np.concatenate((values[:, :half], values[:, -half:]), axis=0)


def rank_normalize(values: np.ndarray) -> np.ndarray:
    """Return the normal-score transform used by modern R-hat and ESS."""
    values = np.asarray(values, dtype=float)
    flat = values.reshape(-1)
    ranks = rankdata(flat, method="average")
    probability = (ranks - 0.375) / (len(flat) + 0.25)
    return ndtri(probability).reshape(values.shape)


def _basic_rhat(values: np.ndarray) -> float:
    split = split_chains(values)
    count = split.shape[1]
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    between = count * float(np.var(np.mean(split, axis=1), ddof=1))
    if within == 0.0:
        return 1.0 if between == 0.0 else math.inf
    return float(math.sqrt(((count - 1.0) / count * within + between / count) / within))


def split_rhat(values: np.ndarray) -> float:
    """Compute rank-normalized folded split-Rhat."""
    split = split_chains(values)
    folded = np.abs(split - np.median(split))
    return max(
        _basic_rhat(rank_normalize(split)),
        _basic_rhat(rank_normalize(folded)),
    )


def _autocovariance(values: np.ndarray) -> np.ndarray:
    centered = values - values.mean()
    count = len(values)
    fft = np.fft.rfft(centered, n=2 * count)
    return np.fft.irfft(fft * np.conjugate(fft), n=2 * count)[:count] / count


def ess(values: np.ndarray) -> float:
    """Estimate effective sample size using Geyer's initial positive sequence."""
    split = split_chains(values)
    chains, count = split.shape
    autocovariance = np.asarray([_autocovariance(chain) for chain in split])
    within = float(np.mean(autocovariance[:, 0] * count / (count - 1.0)))
    between = count * float(np.var(split.mean(axis=1), ddof=1))
    variance = (count - 1.0) / count * within + between / count
    if variance <= 0.0:
        return float(chains * count)
    pairs = []
    for lag in range(1, count - 1, 2):
        rho_1 = 1.0 - (within - float(np.mean(autocovariance[:, lag]))) / variance
        rho_2 = 1.0 - (within - float(np.mean(autocovariance[:, lag + 1]))) / variance
        pair = rho_1 + rho_2
        if pair < 0.0:
            break
        pairs.append(pair)
    tau = (
        1.0
        if not pairs
        else max(
            1.0,
            -1.0 + 2.0 * (1.0 + float(np.minimum.accumulate(pairs).sum())),
        )
    )
    return float(min(chains * count, chains * count / tau))


def mcse_mean(values: np.ndarray, effective_sample_size: float) -> float:
    r"""Estimate Monte Carlo standard error of a posterior mean.

    The reported quantity is

    .. math::

       \operatorname{MCSE}(\bar{x}) = s_x / \sqrt{N_\mathrm{eff}},

    where ``s_x`` is the sample standard deviation of the retained draws and
    ``effective_sample_size`` is the ESS produced by the campaign's documented
    autocorrelation diagnostic.  It measures simulation uncertainty, not
    posterior uncertainty and not observational error; its units therefore
    match those of ``values``.

    Parameters
    ----------
    values
        Retained draws pooled across chains.
    effective_sample_size
        Positive, finite effective sample size for the same estimand.

    Returns
    -------
    float
        Estimated standard error of the Monte Carlo posterior mean.

    Raises
    ------
    ValueError
        If fewer than two finite draws are supplied or ESS is not positive
        and finite.
    """
    draws = np.asarray(values, dtype=float).reshape(-1)
    if draws.size < 2 or not np.all(np.isfinite(draws)):
        raise ValueError("values must contain at least two finite retained draws")
    if not math.isfinite(effective_sample_size) or effective_sample_size <= 0.0:
        raise ValueError("effective_sample_size must be positive and finite")
    return float(np.std(draws, ddof=1) / math.sqrt(effective_sample_size))
