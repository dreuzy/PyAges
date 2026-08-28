# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Inverse-Gaussian prior used by the published Ploemeur calibration."""

from __future__ import annotations

import math
from typing import Sequence

from pyages.calibration.methods.mh.ig_coordinates import physical_moments_to_scipy

BENCHMARK_NAME = "ploemeur_article_scipy_ig_prior"
SHAPE_BOUNDS = (0.1, 100.0)
SCALE_BOUNDS = (0.1, 30.0)
SHIFT_BOUNDS = (0.1, 50.0)


def logpdf(params: Sequence[float], *, normalized: bool = False) -> float:
    """Evaluate the article prior after conversion to physical coordinates.

    The article sampled a uniform density in SciPy ``(shape, scale, shift)``
    coordinates. Its push-forward under ``M=shape*scale`` and
    ``S=scale*shape**(3/2)`` is proportional to ``2/S`` on the transformed,
    non-rectangular support. The Jacobian is essential: omitting it defines a
    different posterior rather than merely changing notation.
    """
    if len(params) != 3:
        raise ValueError("the shifted IG prior requires (M, S, shift)")
    mean, std, shift = (float(value) for value in params)
    shape, scale = physical_moments_to_scipy(mean, std)
    if not all(math.isfinite(value) for value in (shape, scale, shift)):
        return -math.inf
    if not (
        SHAPE_BOUNDS[0] <= shape <= SHAPE_BOUNDS[1]
        and SCALE_BOUNDS[0] <= scale <= SCALE_BOUNDS[1]
        and SHIFT_BOUNDS[0] <= shift <= SHIFT_BOUNDS[1]
    ):
        return -math.inf
    log_density = math.log(2.0) - math.log(std)
    if normalized:
        volume = math.prod(
            upper - lower for lower, upper in (SHAPE_BOUNDS, SCALE_BOUNDS, SHIFT_BOUNDS)
        )
        log_density -= math.log(volume)
    return log_density


__all__ = [
    "BENCHMARK_NAME",
    "SCALE_BOUNDS",
    "SHAPE_BOUNDS",
    "SHIFT_BOUNDS",
    "logpdf",
]
