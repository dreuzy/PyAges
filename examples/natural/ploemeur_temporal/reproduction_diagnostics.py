# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Calculate the diagnostics frozen for the Figure 4 reproduction protocol.

The manuscript reproduction predates the canonical diagnostics now exposed by
``pyages.calibration.methods.mh.diagnostics``. Its archived ESS calculation is
kept independent so rebuilding the historical report does not silently change
registered numbers. Fast tests compare both implementations on mixed and
deliberately shifted chains; new application code must use the canonical
PyAges implementation instead of this module.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import ndtri
from scipy.stats import rankdata

PARAMETERS = ("mu", "sigma", "t0")
QUANTILES = (0.05, 0.10, 0.50, 0.90, 0.95)


def split_chains(chains: np.ndarray) -> np.ndarray:
    """Split every chain into equal first and last halves."""
    half = chains.shape[1] // 2
    if half < 2:
        raise ValueError("At least four draws per chain are required")
    return np.concatenate((chains[:, :half], chains[:, -half:]), axis=0)


def rank_normalize(values: np.ndarray) -> np.ndarray:
    """Apply the Blom normal-score transform used by the frozen protocol."""
    flat = values.reshape(-1)
    ranks = rankdata(flat, method="average")
    probability = (ranks - 0.375) / (len(flat) + 0.25)
    return ndtri(probability).reshape(values.shape)


def _basic_rhat(values: np.ndarray) -> float:
    """Calculate ordinary R-hat after the protocol's internal chain split."""
    values = split_chains(values)
    _chain_count, draw_count = values.shape
    chain_means = values.mean(axis=1)
    between = draw_count * np.var(chain_means, ddof=1)
    within = np.mean(np.var(values, axis=1, ddof=1))
    if within == 0.0:
        return 1.0 if between == 0.0 else np.inf
    variance = (draw_count - 1.0) / draw_count * within + between / draw_count
    return float(np.sqrt(variance / within))


def split_rhat(values: np.ndarray) -> float:
    """Return the frozen rank-normalized folded split-R-hat."""
    split = split_chains(values)
    ranked = rank_normalize(split)
    folded = np.abs(split - np.median(split))
    return max(_basic_rhat(ranked), _basic_rhat(rank_normalize(folded)))


def _autocovariance(values: np.ndarray) -> np.ndarray:
    """Return biased autocovariances for every non-negative lag."""
    values = np.asarray(values, dtype=float)
    centered = values - values.mean()
    count = len(values)
    transformed = np.fft.rfft(centered, n=2 * count)
    return (
        np.fft.irfft(transformed * np.conjugate(transformed), n=2 * count)[:count]
        / count
    )


def effective_sample_size(values: np.ndarray) -> float:
    """Estimate ESS with the initial-positive sequence used in the report."""
    values = split_chains(np.asarray(values, dtype=float))
    chain_count, draw_count = values.shape
    autocovariance = np.asarray([_autocovariance(chain) for chain in values])
    within = np.mean(autocovariance[:, 0] * draw_count / (draw_count - 1.0))
    between = draw_count * np.var(values.mean(axis=1), ddof=1)
    variance = (draw_count - 1.0) / draw_count * within + between / draw_count
    if not np.isfinite(variance) or variance <= 0.0:
        return float(chain_count * draw_count)
    correlations = np.ones(draw_count)
    for lag in range(1, draw_count):
        correlations[lag] = 1.0 - (within - np.mean(autocovariance[:, lag])) / variance
    pairs = []
    for lag in range(1, draw_count - 1, 2):
        pair = correlations[lag] + correlations[lag + 1]
        if pair < 0.0:
            break
        pairs.append(pair)
    if pairs:
        pairs = np.minimum.accumulate(np.asarray(pairs))
        integrated_time = max(
            1.0,
            -1.0 + 2.0 * (1.0 + float(np.sum(pairs))),
        )
    else:
        integrated_time = 1.0
    return float(
        min(
            chain_count * draw_count,
            chain_count * draw_count / integrated_time,
        )
    )


def chain_diagnostics(chains: np.ndarray) -> pd.DataFrame:
    """Summarize R-hat and bulk/tail ESS for each physical parameter."""
    rows = []
    for index, name in enumerate(PARAMETERS):
        values = chains[:, :, index]
        ranked = rank_normalize(values)
        low = (values <= np.quantile(values, 0.05)).astype(float)
        high = (values >= np.quantile(values, 0.95)).astype(float)
        rows.append(
            {
                "parameter": name,
                "split_rhat": split_rhat(values),
                "bulk_ess": effective_sample_size(ranked),
                "tail_ess": min(
                    effective_sample_size(low),
                    effective_sample_size(high),
                ),
            }
        )
    return pd.DataFrame(rows)


def autocorrelation_table(chains: np.ndarray, max_lag: int = 100) -> pd.DataFrame:
    """Return per-chain autocorrelations used by the report figures."""
    rows = []
    for chain in range(chains.shape[0]):
        for parameter, name in enumerate(PARAMETERS):
            covariance = _autocovariance(chains[chain, :, parameter])
            acf = covariance[: max_lag + 1] / covariance[0]
            rows.extend(
                {
                    "chain": chain + 1,
                    "parameter": name,
                    "lag": lag,
                    "autocorrelation": value,
                }
                for lag, value in enumerate(acf)
            )
    return pd.DataFrame(rows)


def summarize_chains(chains: np.ndarray, experiment: str) -> pd.DataFrame:
    """Return posterior moments and registered quantiles for one experiment."""
    flat = chains.reshape(-1, 3)
    values = {
        "mu": flat[:, 0],
        "sigma": flat[:, 1],
        "t0": flat[:, 2],
        "mu_plus_t0": flat[:, 0] + flat[:, 2],
    }
    rows = []
    for name, sample in values.items():
        quantile = np.quantile(sample, QUANTILES)
        rows.append(
            {
                "experiment": experiment,
                "parameter": name,
                "mean": np.mean(sample),
                "median": np.median(sample),
                "sd": np.std(sample, ddof=1),
                **{
                    f"q{int(q * 100):02d}": value
                    for q, value in zip(QUANTILES, quantile, strict=False)
                },
            }
        )
    return pd.DataFrame(rows)


def joint_indices(total: int, count: int, seed: int) -> np.ndarray:
    """Choose reproducible joint posterior rows without replacement."""
    rng = np.random.default_rng(seed)
    return rng.choice(total, size=min(total, count), replace=False)


__all__ = [
    "autocorrelation_table",
    "chain_diagnostics",
    "effective_sample_size",
    "joint_indices",
    "rank_normalize",
    "split_chains",
    "split_rhat",
    "summarize_chains",
]
