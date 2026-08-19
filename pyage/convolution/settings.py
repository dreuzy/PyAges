"""Numerical settings for tracer-driven convolution grids."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class TracerGridSettings:
    """Accuracy and safety controls for the cached tracer-response grid."""

    absolute_tolerance_factor: float = 5.0e-4
    relative_tolerance: float = 2.0e-2
    linear_curvature_factor: float = 0.1
    max_subdivisions: int = 20
    max_bins: int = 20_000
    floating_weight_epsilon_factor: float = 64.0

    def __post_init__(self) -> None:
        for name in (
            "absolute_tolerance_factor",
            "relative_tolerance",
            "linear_curvature_factor",
            "floating_weight_epsilon_factor",
        ):
            value = getattr(self, name)
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        for name, minimum in (("max_subdivisions", 0), ("max_bins", 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")


DEFAULT_TRACER_GRID_SETTINGS = TracerGridSettings()


__all__ = ["DEFAULT_TRACER_GRID_SETTINGS", "TracerGridSettings"]
