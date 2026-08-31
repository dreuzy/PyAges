# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# Purpose: Compute split R-hat, ESS, and MCSE from unpooled MCMC chains.

"""Dependency-light convergence diagnostics for multi-chain MCMC draws.

The implementations in this module follow the rank-normalized split-R-hat and
effective-sample-size recommendations of Vehtari et al. (2021).

Every public function accepts draws arranged as ``(n_chains, n_draws)``.
Keeping that contract explicit prevents accidentally treating pooled draws as
independent.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtri
from scipy.stats import rankdata


def _validate_chains(values: np.ndarray) -> np.ndarray:
    """Return a finite floating two-dimensional chain array."""
    draws = np.asarray(values, dtype=float)
    if draws.ndim != 2 or draws.shape[0] < 2 or draws.shape[1] < 4:
        raise ValueError("values must contain at least two chains and four draws")
    if not np.all(np.isfinite(draws)):
        raise ValueError("values must contain only finite draws")
    return draws


def split_chains(values: np.ndarray) -> np.ndarray:
    """Split every chain into equal first and last halves.

    The middle draw is discarded when a chain has an odd number of draws.
    The returned array therefore has ``2 * n_chains`` rows and
    ``floor(n_draws / 2)`` columns.
    """
    draws = _validate_chains(values)
    half = draws.shape[1] // 2
    return np.concatenate((draws[:, :half], draws[:, -half:]), axis=0)


def rank_normalize(values: np.ndarray) -> np.ndarray:
    """Transform pooled ranks to normal scores while preserving chain shape.

    Average ranks are used for ties and Blom's offset keeps the probabilities
    strictly inside ``(0, 1)``.

    Consequently, finite inputs always produce finite normal scores.
    """
    draws = _validate_chains(values)
    return _rank_normalize(draws)


def _rank_normalize(draws: np.ndarray) -> np.ndarray:
    """Rank-normalize an already validated two-dimensional draw array."""
    flat = draws.reshape(-1)
    ranks = rankdata(flat, method="average")
    probabilities = (ranks - 0.375) / (flat.size + 0.25)
    return ndtri(probabilities).reshape(draws.shape)


def _basic_rhat(split: np.ndarray) -> float:
    """Calculate ordinary R-hat for draws that are already split."""
    count = split.shape[1]
    within = float(np.mean(np.var(split, axis=1, ddof=1)))
    between_over_count = float(np.var(np.mean(split, axis=1), ddof=1))
    if within == 0.0:
        return math.nan if between_over_count == 0.0 else math.inf
    variance = (count - 1.0) / count * within + between_over_count
    return float(math.sqrt(max(variance / within, 0.0)))


def split_rhat(values: np.ndarray) -> float:
    """Return rank-normalized folded split-R-hat.

    Each chain is split exactly once.

    R-hat is then calculated both for the rank-normalized draws (location
    mixing) and for rank-normalized absolute deviations from their pooled
    median (scale mixing). The larger value is returned.

    A completely constant ensemble returns infinity rather than a misleading
    value of one. Identical stuck chains are not evidence of convergence.
    """
    draws = _validate_chains(values)
    if not np.any(draws != draws.flat[0]):
        return math.inf

    split = split_chains(draws)
    rank_rhat = _basic_rhat(_rank_normalize(split))

    # Fold the already split draws. For odd original lengths this deliberately
    # excludes the discarded middle draw from both the median and the ranks.
    folded = np.abs(split - np.median(split))
    folded_rhat = _basic_rhat(_rank_normalize(folded))

    finite_diagnostics = [
        diagnostic
        for diagnostic in (rank_rhat, folded_rhat)
        if not math.isnan(diagnostic)
    ]
    return max(finite_diagnostics, default=math.inf)


def _autocovariance(values: np.ndarray) -> np.ndarray:
    """Return biased autocovariances for every non-negative lag."""
    centered = values - np.mean(values)
    count = centered.size
    transformed = np.fft.rfft(centered, n=2 * count)
    return (
        np.fft.irfft(transformed * np.conjugate(transformed), n=2 * count)[:count]
        / count
    )


def _ess_from_split(split: np.ndarray) -> float:
    """Estimate ESS for an array that has already been split.

    This follows Stan's initial-positive and initial-monotone sequence,
    including the antithetic-chain lower bound on the integrated
    autocorrelation time.

    Consequently, ESS may legitimately exceed the raw draw count, up to
    ``N * log10(N)``.
    """
    if not np.any(split != split.flat[0]):
        # A transformed intermediate can be constant even when the original
        # draws are not (for example a short tail-indicator sequence). It then
        # carries no autocorrelation penalty. Public callers separately reject
        # an actually constant sampled quantity as degenerate.
        return float(split.size)

    # ESS is invariant under affine rescaling.  Scaling here avoids underflow
    # for perfectly valid chains whose numerical amplitude is extremely small.
    centered = split - np.mean(split)
    scale = float(np.max(np.abs(centered)))
    if scale == 0.0 or not math.isfinite(scale):
        return 0.0
    scaled = centered / scale

    chain_count, draw_count = scaled.shape
    autocovariances = np.asarray(
        [_autocovariance(chain) for chain in scaled], dtype=float
    )
    within = float(np.mean(autocovariances[:, 0] * draw_count / (draw_count - 1.0)))
    between_over_count = float(np.var(np.mean(scaled, axis=1), ddof=1))
    variance = (draw_count - 1.0) / draw_count * within + between_over_count
    if variance <= 0.0 or not math.isfinite(variance):
        return 0.0

    total = float(chain_count * draw_count)
    correlations = np.zeros(draw_count, dtype=float)
    even_correlation = 1.0
    correlations[0] = even_correlation
    odd_correlation = 1.0 - (within - float(np.mean(autocovariances[:, 1]))) / variance
    correlations[1] = odd_correlation

    # Build Geyer's initial positive sequence. It retains rho_0 and rho_1 first,
    # then accepts (rho_2, rho_3), (rho_4, rho_5), ... while each pair sum is
    # non-negative. A final positive even term is retained on its own.
    lag = 1
    while lag < draw_count - 3 and even_correlation + odd_correlation > 0.0:
        even_correlation = (
            1.0 - (within - float(np.mean(autocovariances[:, lag + 1]))) / variance
        )
        odd_correlation = (
            1.0 - (within - float(np.mean(autocovariances[:, lag + 2]))) / variance
        )
        if even_correlation + odd_correlation >= 0.0:
            correlations[lag + 1] = even_correlation
            correlations[lag + 2] = odd_correlation
        lag += 2

    maximum_lag = lag - 2
    if even_correlation > 0.0:
        correlations[maximum_lag + 1] = even_correlation

    # Enforce Geyer's initial monotone sequence. A rising adjacent-pair sum is
    # replaced by the previous pair's average; the previous pair is unchanged.
    lag = 1
    while lag <= maximum_lag - 2:
        previous_pair = correlations[lag - 1] + correlations[lag]
        current_pair = correlations[lag + 1] + correlations[lag + 2]
        if current_pair > previous_pair:
            correlations[lag + 1] = previous_pair / 2.0
            correlations[lag + 2] = previous_pair / 2.0
        lag += 2

    integrated_time = (
        -1.0
        + 2.0 * float(np.sum(correlations[: maximum_lag + 1]))
        + float(np.sum(correlations[maximum_lag + 1 : maximum_lag + 2]))
    )
    integrated_time = max(integrated_time, 1.0 / math.log10(total))
    if not math.isfinite(integrated_time):
        return 0.0
    return total / integrated_time


def ess(values: np.ndarray) -> float:
    """Estimate effective sample size with Geyer's monotone sequence.

    The chains are split once before estimating their joint autocorrelation.

    Antithetic chains may yield an estimate above the retained split-draw count;
    the Stan lower bound on autocorrelation time caps it at ``N * log10(N)``.

    A completely constant ensemble returns zero to prevent a stuck sampler from
    appearing well sampled.
    """
    draws = _validate_chains(values)
    if not np.any(draws != draws.flat[0]):
        return 0.0
    return _ess_from_split(split_chains(draws))


def bulk_ess(values: np.ndarray) -> float:
    """Return rank-normalized ESS for the bulk of the distribution."""
    draws = _validate_chains(values)
    if not np.any(draws != draws.flat[0]):
        return 0.0
    split = split_chains(draws)
    return _ess_from_split(_rank_normalize(split))


def tail_ess(values: np.ndarray, probability: float = 0.05) -> float:
    """Return the smaller lower- and upper-tail quantile ESS.

    ``probability`` defines lower and upper empirical quantiles.

    Their CDF indicators, ``x <= q_probability`` and
    ``x <= q_(1-probability)``, measure quantile stability. The complement of
    the latter is the upper-tail event and has the same autocorrelation ESS.
    """
    draws = _validate_chains(values)
    if not math.isfinite(probability) or probability <= 0.0 or probability >= 0.5:
        raise ValueError("probability must be finite and strictly between 0 and 0.5")
    if not np.any(draws != draws.flat[0]):
        return 0.0

    lower, upper = np.quantile(draws, (probability, 1.0 - probability))
    lower_indicator = np.asarray(draws <= lower, dtype=float)
    upper_indicator = np.asarray(draws <= upper, dtype=float)
    return min(
        _ess_from_split(split_chains(lower_indicator)),
        _ess_from_split(split_chains(upper_indicator)),
    )


def mcse_mean(values: np.ndarray, effective_sample_size: float | None = None) -> float:
    r"""Estimate Monte Carlo standard error of the posterior mean.

    ``values`` must retain its ``(n_chains, n_draws)`` structure.  When
    ``effective_sample_size`` is omitted, :func:`ess` estimates it from the
    raw draws.  Supplying an ESS is useful when a caller has already calculated
    and recorded the diagnostic for the same estimand.

    The result is ``sample_sd / sqrt(ESS)`` and has the same units as the
    sampled parameter.  It measures simulation uncertainty, not posterior or
    observational uncertainty.  A constant sample has zero empirical MCSE,
    although :func:`split_rhat` and :func:`ess` deliberately mark that ensemble
    as degenerate.
    """
    draws = _validate_chains(values)
    if effective_sample_size is not None and (
        not math.isfinite(effective_sample_size) or effective_sample_size <= 0.0
    ):
        raise ValueError("effective_sample_size must be positive and finite")

    sample_sd = float(np.std(draws, ddof=1))
    if sample_sd == 0.0:
        return 0.0

    effective = ess(draws) if effective_sample_size is None else effective_sample_size
    if not math.isfinite(effective) or effective <= 0.0:
        raise ValueError("effective_sample_size must be positive and finite")
    return float(sample_sd / math.sqrt(effective))


__all__ = [
    "bulk_ess",
    "ess",
    "mcse_mean",
    "rank_normalize",
    "split_chains",
    "split_rhat",
    "tail_ess",
]
