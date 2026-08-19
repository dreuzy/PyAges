"""Explicit conversions for first-order radioactive decay parameters."""

from collections.abc import Mapping
from typing import Any

import numpy as np


def rate_from_half_life(half_life: float) -> float:
    """Return beta = ln(2) / half_life, with times expressed consistently."""
    value = float(half_life)
    if value <= 0:
        raise ValueError(f"half_life must be positive, got {value}")
    return float(np.log(2.0) / value)


def rate_from_mean_lifetime(mean_lifetime: float) -> float:
    """Return beta = 1 / mean_lifetime."""
    value = float(mean_lifetime)
    if value <= 0:
        raise ValueError(f"decay_mean_lifetime must be positive, got {value}")
    return 1.0 / value


def rate_from_config(config: Mapping[str, Any]) -> float | None:
    """Read exactly one explicit decay convention from a tracer mapping."""
    has_half_life = "half_life" in config
    has_mean_lifetime = "decay_mean_lifetime" in config
    if has_half_life and has_mean_lifetime:
        raise ValueError("Specify only half_life or decay_mean_lifetime, not both")
    if has_half_life:
        return rate_from_half_life(config["half_life"])
    if has_mean_lifetime:
        return rate_from_mean_lifetime(config["decay_mean_lifetime"])
    return None
