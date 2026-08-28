# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Define accuracy guards and resource limits for adaptive tracer grids.

The controls resolve the tracer response, while hard subdivision and bin limits
turn non-convergence into an explicit error instead of a silent approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class TracerGridSettings:
    r"""Accuracy and safety controls for the cached tracer-response grid.

    The adaptive grid resolves the tracer response :math:`K(\tau)`, not the
    LPM probability density. A bin is accepted when the range of the left,
    midpoint, and right responses satisfies

    .. math::

       \Delta K \leq f_a\max(K_g,\epsilon) + f_r K_{\mathrm{local}}.

    Here ``absolute_tolerance_factor`` is :math:`f_a`,
    ``relative_tolerance`` is :math:`f_r`, and :math:`K_g` is the largest
    absolute response encountered so far. These dimensionless controls apply
    to tracer concentrations in the tracer's declared unit; ages and bin
    widths are decimal years.

    Parameters
    ----------
    absolute_tolerance_factor : float
        Global response-scale factor :math:`f_a`. The default is ``5e-4``.
    relative_tolerance : float
        Local response-scale factor :math:`f_r`. The default is ``2e-2``.
    linear_curvature_factor : float
        Fraction of the preceding acceptance tolerance allowed for midpoint
        curvature before integration falls back from the affine formula to a
        midpoint contribution. The default is ``0.1``.
    max_subdivisions : int
        Maximum bisection depth per initial tracer interval. Exhaustion raises
        :class:`~pyages.convolution.models.ConvolutionError`; it never silently
        accepts an unresolved bin.
    max_bins : int
        Hard upper bound on prepared bins, limiting memory and run time.
    floating_weight_epsilon_factor : float
        Multiplier of machine epsilon used only to clip round-off-sized
        negative CDF differences or partial moments. Larger inconsistencies
        remain errors.

    Notes
    -----
    These settings are numerical controls, not physical model parameters and
    not a formal bound on total convolution error. Record non-default values
    and test sensitivity for publication calculations. The algorithm and its
    validation are described in ``docs/scientific-methods.md`` and
    ``docs/convolution-method-evolution-report.md``.
    """

    absolute_tolerance_factor: float = 5.0e-4
    relative_tolerance: float = 2.0e-2
    linear_curvature_factor: float = 0.1
    max_subdivisions: int = 20
    max_bins: int = 20_000
    floating_weight_epsilon_factor: float = 64.0

    def __post_init__(self) -> None:
        """Reject non-finite, negative, or non-integral grid controls."""
        # Tolerance factors may be zero for strict experiments, but never
        # negative or non-finite.
        for name in (
            "absolute_tolerance_factor",
            "relative_tolerance",
            "linear_curvature_factor",
            "floating_weight_epsilon_factor",
        ):
            value = getattr(self, name)
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        # Booleans are integers in Python; reject them explicitly because they
        # are nonsensical resource limits.
        for name, minimum in (("max_subdivisions", 0), ("max_bins", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")


DEFAULT_TRACER_GRID_SETTINGS = TracerGridSettings()


__all__ = ["DEFAULT_TRACER_GRID_SETTINGS", "TracerGridSettings"]
