# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file validates prior bounds and moves endpoint probabilities just inside
# zero and one so numerical quantile calculations remain finite.

"""Shared finite-bound and probability validation for MH priors."""

from __future__ import annotations

import math

import numpy as np


def open_unit_probability(probability: float) -> float:
    """Return one validated probability strictly inside the unit interval."""
    if isinstance(probability, (bool, np.bool_)):
        raise ValueError("quantile probability must be finite and in [0, 1]")
    try:
        probability = float(probability)
    except (TypeError, ValueError) as exc:
        raise ValueError("quantile probability must be finite and in [0, 1]") from exc
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("quantile probability must be finite and in [0, 1]")
    return float(
        np.clip(
            probability,
            np.nextafter(0.0, 1.0),
            np.nextafter(1.0, 0.0),
        )
    )


def validated_bounds(minimum: float, maximum: float) -> tuple[float, float]:
    """Return one finite, strictly increasing operational interval."""
    try:
        minimum = float(minimum)
        maximum = float(maximum)
    except (TypeError, ValueError) as exc:
        raise ValueError("marginal bounds must be finite numbers") from exc
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        raise ValueError("marginal bounds must be finite numbers")
    if maximum <= minimum:
        raise ValueError("marginal bounds must be strictly increasing")
    return minimum, maximum


__all__ = ["open_unit_probability", "validated_bounds"]
