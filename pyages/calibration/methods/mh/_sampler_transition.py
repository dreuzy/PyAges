# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file applies the Metropolis--Hastings acceptance rule and keeps parameters,
# probability, fit quality, and predictions together when selecting the next state.

"""Select an accepted or rejected Metropolis--Hastings transition state."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class MHState:
    """All values that must move together when a candidate is accepted."""

    params: list[float]
    log_posterior: float
    chi_square: float
    concentrations: list[float]


def select_transition(
    current: MHState,
    candidate: MHState,
    *,
    log_hastings: float,
    rng: np.random.Generator,
) -> tuple[MHState, bool]:
    """Return the selected state while preserving the seeded draw protocol."""
    if candidate.log_posterior + log_hastings >= current.log_posterior:
        return candidate, True
    log_acceptance = candidate.log_posterior - current.log_posterior + log_hastings
    if np.log(rng.random()) < log_acceptance:
        return candidate, True
    return current, False


__all__ = ["MHState", "select_transition"]
