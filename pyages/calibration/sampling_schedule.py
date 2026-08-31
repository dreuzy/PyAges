# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Pure sample-count calculations shared by MCMC configuration layers.

This module contains no sampler, Pydantic, or workflow dependencies. It is the
single source of truth for the strict burn-in/thinning convention and for the
algorithmic ceiling used to reject impossible split-chain ESS gates.
"""

from __future__ import annotations

import math


def _positive_integer(value: object, name: str) -> int:
    """Return ``value`` as a positive integer or reject it."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def strict_retained_sample_count(
    nstep: int,
    burn_in: float,
    nskip: int,
) -> int:
    """Return the exact number of states retained by an MCMC chain.

    Iteration indices are zero based. An iteration ``i`` is retained exactly
    when ``i > burn_in * nstep`` and ``i % nskip == 0``. The strict inequality
    is important when the burn-in threshold itself is a multiple of
    ``nskip``.
    """
    nstep = _positive_integer(nstep, "nstep")
    nskip = _positive_integer(nskip, "nskip")
    if isinstance(burn_in, bool) or not isinstance(burn_in, (int, float)):
        raise ValueError("burn_in must be a finite number in [0, 1)")
    burn_in = float(burn_in)
    if not math.isfinite(burn_in) or not 0.0 <= burn_in < 1.0:
        raise ValueError("burn_in must be a finite number in [0, 1)")

    threshold = burn_in * nstep
    first = (math.floor(threshold / nskip) + 1) * nskip
    if first >= nstep:
        return 0
    return 1 + (nstep - 1 - first) // nskip


def maximum_split_ess(chains: int, retained_sample_count: int) -> float:
    """Return Stan's antithetic ESS ceiling for equally sized split chains.

    Odd final draws are discarded when each chain is split in half. Stan's
    rank-normalized ESS estimate is capped at ``N * log10(N)``, where ``N`` is
    the resulting total number of split-chain draws. Fewer than two retained
    draws per chain cannot form split chains and therefore have a zero ceiling.
    """
    chains = _positive_integer(chains, "chains")
    if (
        isinstance(retained_sample_count, bool)
        or not isinstance(retained_sample_count, int)
        or retained_sample_count < 0
    ):
        raise ValueError("retained_sample_count must be a non-negative integer")
    split_draws = chains * 2 * (retained_sample_count // 2)
    if split_draws == 0:
        return 0.0
    return split_draws * math.log10(split_draws)


__all__ = ["maximum_split_ess", "strict_retained_sample_count"]
