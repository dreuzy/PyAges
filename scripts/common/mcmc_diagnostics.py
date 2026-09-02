# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Expose canonical PyAges MCMC diagnostics to repository-only scripts.

Article and qualification tooling used to carry a second implementation of
split R-hat and ESS. The maintained functions now come directly from the
library so diagnostic edge cases and numerical improvements cannot drift. The
one local adapter, :func:`mcse_mean`, retains the historical convenience of
accepting already-pooled one-dimensional draws when an ESS is supplied.
"""

from __future__ import annotations

import math

import numpy as np

from pyages.calibration.methods.mh.diagnostics import (
    ess,
    rank_normalize,
    split_chains,
    split_rhat,
)


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


__all__ = ["ess", "mcse_mean", "rank_normalize", "split_chains", "split_rhat"]
