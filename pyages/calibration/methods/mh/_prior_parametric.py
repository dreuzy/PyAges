# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file evaluates normal and uniform parameter priors after restricting them
# to the finite calibration range, including their resulting mean and variance.

"""Parametric MH prior density and bounded-moment calculations."""

from __future__ import annotations

import math

from scipy.stats import truncnorm


def normal_pdf(x: float, mean: float, std: float) -> float:
    """Evaluate one normal density."""
    if not math.isfinite(std) or std <= 0.0:
        raise ValueError("Normal prior std must be finite and positive")
    numerator = math.exp(-((x - mean) ** 2) / (2.0 * std**2))
    denominator = math.sqrt(2.0 * math.pi * std**2)
    return numerator / denominator


def effective_parametric_support(
    distribution: str,
    first: float,
    second: float,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    """Intersect one prior support with the finite calibration range."""
    if distribution == "normal":
        lower, upper = minimum, maximum
    elif distribution == "uniform":
        lower, upper = max(minimum, first), min(maximum, second)
    else:
        raise ValueError(f"Unsupported prior distribution: {distribution}")
    if upper <= lower:
        raise ValueError("Prior has no positive-width effective support")
    return lower, upper


def bounded_parametric_moments(
    distribution: str,
    first: float,
    second: float,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    """Return moments conditional on the operational calibration range."""
    lower, upper = effective_parametric_support(
        distribution,
        first,
        second,
        minimum,
        maximum,
    )
    if distribution == "uniform":
        return 0.5 * (lower + upper), (upper - lower) ** 2 / 12.0
    mean, variance = truncnorm.stats(
        (lower - first) / second,
        (upper - first) / second,
        loc=first,
        scale=second,
        moments="mv",
    )
    return float(mean), float(variance)


__all__ = [
    "bounded_parametric_moments",
    "effective_parametric_support",
    "normal_pdf",
]
