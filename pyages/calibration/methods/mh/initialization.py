# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Pure construction of reproducible initial states for MH chain ensembles."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.stats import truncnorm

from pyages.calibration.methods.mh.ensemble_config import MHInitializationConfig


def _parameter_names(lpm: Any) -> tuple[str, ...]:
    """Return the model's canonical parameter order."""
    if hasattr(lpm, "get_param_names"):
        names = tuple(lpm.get_param_names())
    elif hasattr(lpm, "p"):
        names = tuple(lpm.p)
    else:
        raise TypeError("lpm must expose get_param_names() or p")
    if not names or any(not isinstance(name, str) for name in names):
        raise ValueError("lpm must expose at least one named parameter")
    if len(set(names)) != len(names):
        raise ValueError("lpm parameter names must be unique")
    return names


def _parameter_bounds(lpm: Any, names: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    """Return validated physical bounds in canonical order."""
    try:
        lower = np.asarray([lpm.get_p_min(name) for name in names], dtype=float)
        upper = np.asarray([lpm.get_p_max(name) for name in names], dtype=float)
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        raise ValueError("lpm parameter bounds must be numeric") from exc
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
        raise ValueError("lpm parameter bounds must be finite")
    if np.any(upper <= lower):
        raise ValueError("lpm parameter bounds must be strictly increasing")
    return lower, upper


def _validated_seeds(seeds: Sequence[int], chain_count: int) -> tuple[int, ...]:
    """Return exactly one non-negative initialization seed per chain."""
    try:
        values = tuple(seeds)
    except TypeError as exc:
        raise ValueError("seeds must provide one integer per chain") from exc
    if len(values) != chain_count:
        raise ValueError(
            f"seeds must contain exactly {chain_count} values, got {len(values)}"
        )
    if any(
        isinstance(seed, (bool, np.bool_))
        or not isinstance(seed, (int, np.integer))
        or int(seed) < 0
        for seed in values
    ):
        raise ValueError("seeds must be non-negative integers")
    normalized = tuple(int(seed) for seed in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError("seeds must be distinct")
    return normalized


def _validate_state(
    state: Mapping[str, Any],
    names: Sequence[str],
    lower: np.ndarray,
    upper: np.ndarray,
) -> dict[str, float]:
    """Copy one state after checking names, finiteness, and LPM bounds."""
    provided = tuple(state)
    missing = [name for name in names if name not in state]
    extra = [name for name in provided if name not in names]
    if missing or extra:
        raise ValueError(
            "initial state must define exactly the LPM parameters "
            f"{list(names)} (missing={missing}, extra={extra})"
        )
    values: list[float] = []
    for name in names:
        raw_value = state[name]
        if isinstance(raw_value, (bool, np.bool_)):
            raise ValueError(f"initial value for {name!r} must be a finite number")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"initial value for {name!r} must be a finite number"
            ) from exc
        if not math.isfinite(value):
            raise ValueError(f"initial value for {name!r} must be finite")
        values.append(value)
    array = np.asarray(values)
    if np.any(array < lower) or np.any(array > upper):
        bounds = {
            name: [float(minimum), float(maximum)]
            for name, minimum, maximum in zip(names, lower, upper, strict=True)
        }
        raise ValueError(f"initial state is outside the LPM bounds {bounds}")
    return dict(zip(names, values, strict=True))


def _require_prior(prior: Any, names: Sequence[str]) -> None:
    """Ensure an active, loaded prior covers every model parameter."""
    if prior is None or getattr(prior, "option", True) is not True:
        raise ValueError("prior initialization requires an enabled prior")
    typ = getattr(prior, "typ", None)
    if typ == "parametric":
        distributions = getattr(prior, "distributions", {})
        parameters = getattr(prior, "parameters", {})
        missing = [
            name
            for name in names
            if name not in distributions or name not in parameters
        ]
    elif typ == "empirical":
        parameters = getattr(prior, "parameters", {})
        missing = [name for name in names if name not in parameters]
    else:
        raise ValueError("prior must be parametric or empirical")
    if missing:
        raise ValueError(f"prior must be loaded for parameters {missing}")


def _sample_parametric_value(
    prior: Any,
    name: str,
    minimum: float,
    maximum: float,
    rng: np.random.Generator,
) -> float:
    """Draw one value from a parametric prior restricted to LPM bounds."""
    return _parametric_quantile(
        prior,
        name,
        minimum,
        maximum,
        float(rng.random()),
    )


def _open_probability(probability: float) -> float:
    """Return a finite probability strictly inside the unit interval."""
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("quantile probability must be finite and in [0, 1]")
    return float(
        np.clip(
            probability,
            np.nextafter(0.0, 1.0),
            np.nextafter(1.0, 0.0),
        )
    )


def _parametric_quantile(
    prior: Any,
    name: str,
    minimum: float,
    maximum: float,
    probability: float,
) -> float:
    """Invert one parametric prior after truncation to physical bounds."""
    distribution = prior.distributions[name]
    first, second = (float(item) for item in prior.parameters[name])
    probability = _open_probability(probability)
    if distribution == "normal":
        if not math.isfinite(first) or not math.isfinite(second) or second <= 0.0:
            raise ValueError(f"Normal prior parameters are invalid for {name}")
        standardized_minimum = (minimum - first) / second
        standardized_maximum = (maximum - first) / second
        value = float(
            truncnorm.ppf(
                probability,
                standardized_minimum,
                standardized_maximum,
                loc=first,
                scale=second,
            )
        )
        if not math.isfinite(value):
            raise ValueError(f"Normal prior has no numerically usable mass for {name}")
        return float(np.clip(value, minimum, maximum))
    if distribution == "uniform":
        if not math.isfinite(first) or not math.isfinite(second) or second <= first:
            raise ValueError(f"Uniform prior bounds are invalid for {name}")
        effective_minimum = max(minimum, first)
        effective_maximum = min(maximum, second)
        if effective_maximum <= effective_minimum:
            raise ValueError(f"Uniform prior has no positive support for {name}")
        return effective_minimum + probability * (effective_maximum - effective_minimum)
    raise ValueError(f"Unsupported prior distribution: {distribution}")


def _empirical_grid(
    prior: Any, name: str, minimum: float, maximum: float
) -> tuple[np.ndarray, np.ndarray]:
    """Clip one empirical density grid precisely to the model bounds."""
    try:
        histogram = np.asarray(prior.parameters[name], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Empirical prior is invalid for {name}") from exc
    if histogram.ndim != 2 or histogram.shape[1] != 2 or histogram.shape[0] < 2:
        raise ValueError(f"Empirical prior is invalid for {name}")
    values, density = histogram.T
    if (
        not np.all(np.isfinite(values))
        or not np.all(np.isfinite(density))
        or np.any(np.diff(values) <= 0.0)
        or np.any(density < 0.0)
    ):
        raise ValueError(f"Empirical prior is invalid for {name}")
    support_minimum = max(minimum, float(values[0]))
    support_maximum = min(maximum, float(values[-1]))
    if support_maximum <= support_minimum:
        raise ValueError(f"Empirical prior has no positive support for {name}")
    interior = (values > support_minimum) & (values < support_maximum)
    clipped_values = np.concatenate(
        ([support_minimum], values[interior], [support_maximum])
    )
    clipped_density = np.interp(clipped_values, values, density)
    return clipped_values, clipped_density


def _sample_empirical_value(
    prior: Any,
    name: str,
    minimum: float,
    maximum: float,
    rng: np.random.Generator,
) -> float:
    """Draw continuously from a bounded piecewise-linear empirical density."""
    return _empirical_quantile(
        prior,
        name,
        minimum,
        maximum,
        float(rng.random()),
    )


def _empirical_quantile(
    prior: Any,
    name: str,
    minimum: float,
    maximum: float,
    probability: float,
) -> float:
    """Invert a bounded piecewise-linear empirical density exactly."""
    values, density = _empirical_grid(prior, name, minimum, maximum)
    widths = np.diff(values)
    increments = 0.5 * (density[:-1] + density[1:]) * widths
    total = float(np.sum(increments))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError(f"Empirical prior has no positive mass for {name}")
    target = _open_probability(probability) * total
    cumulative = np.concatenate(([0.0], np.cumsum(increments)))
    cell = min(
        int(np.searchsorted(cumulative, target, side="right") - 1), len(widths) - 1
    )
    remaining = target - cumulative[cell]
    left_density = density[cell]
    slope = (density[cell + 1] - left_density) / widths[cell]
    if abs(slope) <= np.finfo(float).eps:
        offset = remaining / left_density if left_density > 0.0 else 0.0
    else:
        discriminant = max(0.0, left_density**2 + 2.0 * slope * remaining)
        offset = (-left_density + math.sqrt(discriminant)) / slope
    return float(np.clip(values[cell] + offset, values[cell], values[cell + 1]))


def _bounded_marginal_quantile(
    prior: Any,
    name: str,
    minimum: float,
    maximum: float,
    probability: float,
) -> float:
    """Map probability mass to one physical or active-prior marginal."""
    probability = _open_probability(probability)
    if prior is None or getattr(prior, "option", False) is not True:
        return minimum + probability * (maximum - minimum)
    if prior.typ == "parametric":
        return _parametric_quantile(
            prior,
            name,
            minimum,
            maximum,
            probability,
        )
    if prior.typ == "empirical":
        return _empirical_quantile(
            prior,
            name,
            minimum,
            maximum,
            probability,
        )
    raise ValueError("prior must be parametric or empirical")


def _parametric_map_value(
    prior: Any, name: str, minimum: float, maximum: float
) -> float:
    """Return a bounded MAP-like value for one parametric prior."""
    distribution = prior.distributions[name]
    first, second = (float(item) for item in prior.parameters[name])
    if distribution == "normal":
        if not math.isfinite(first) or not math.isfinite(second) or second <= 0:
            raise ValueError(f"Normal prior parameters are invalid for {name}")
        return float(np.clip(first, minimum, maximum))
    if distribution == "uniform":
        effective_minimum = max(minimum, first)
        effective_maximum = min(maximum, second)
        if effective_maximum <= effective_minimum:
            raise ValueError(f"Uniform prior has no positive support for {name}")
        return 0.5 * (effective_minimum + effective_maximum)
    raise ValueError(f"Unsupported prior distribution: {distribution}")


def _empirical_map_value(
    prior: Any, name: str, minimum: float, maximum: float
) -> float:
    """Return the bounded grid mode for one empirical prior."""
    values, density = _empirical_grid(prior, name, minimum, maximum)
    if not np.any(density > 0.0):
        raise ValueError(f"Empirical prior has no positive mass for {name}")
    return float(values[np.argmax(density)])


def _prior_state(
    prior: Any,
    names: Sequence[str],
    lower: np.ndarray,
    upper: np.ndarray,
    rng: np.random.Generator | None,
    *,
    sample: bool,
) -> dict[str, float]:
    """Construct one sampled or MAP-like state from an already loaded prior."""
    _require_prior(prior, names)
    state: dict[str, float] = {}
    for index, name in enumerate(names):
        minimum, maximum = float(lower[index]), float(upper[index])
        if sample:
            if rng is None:
                raise AssertionError("sampled initialization requires an RNG")
            if prior.typ == "parametric":
                value = _sample_parametric_value(prior, name, minimum, maximum, rng)
            else:
                value = _sample_empirical_value(prior, name, minimum, maximum, rng)
        elif prior.typ == "parametric":
            value = _parametric_map_value(prior, name, minimum, maximum)
        else:
            value = _empirical_map_value(prior, name, minimum, maximum)
        state[name] = value
    return state


def _model_default_state(lpm: Any, names: Sequence[str]) -> dict[str, float]:
    """Copy the current model parameters without mutating the model."""
    if hasattr(lpm, "get_parameters_to_array"):
        values = lpm.get_parameters_to_array()
        if len(values) != len(names):
            raise ValueError("lpm default parameter count does not match its names")
        return dict(zip(names, values, strict=True))
    try:
        return {name: lpm.p[name] for name in names}
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError("lpm does not expose default parameter values") from exc


def _has_prior_support(
    lpm: Any,
    prior: Any,
    names: Sequence[str],
    state: Mapping[str, float],
) -> bool:
    """Return whether one bounded state belongs to the active prior support."""
    if prior is None or getattr(prior, "option", False) is not True:
        return True
    _require_prior(prior, names)
    log_density = prior.log_evaluate(lpm, [state[name] for name in names])
    return math.isfinite(float(log_density))


def _bounds_stratified_states(
    lpm: Any,
    prior: Any,
    config: MHInitializationConfig,
    names: Sequence[str],
    lower: np.ndarray,
    upper: np.ndarray,
    normalized_seeds: tuple[int, ...],
    chain_count: int,
) -> list[dict[str, float]]:
    """Draw a Latin hypercube over physical or active-prior marginal mass.

    With no active prior, probability is mapped uniformly to the physical LPM
    bounds. With an active factorized prior, each stratum instead contains the
    same effective marginal prior mass after truncation to those bounds. This
    avoids impossible outer physical strata when a prior has narrower support.
    """
    if prior is not None and getattr(prior, "option", False) is True:
        _require_prior(prior, names)

    plan_rng = np.random.default_rng(
        np.random.SeedSequence(normalized_seeds, spawn_key=(0,))
    )
    chain_rngs = tuple(
        np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(1,)))
        for seed in normalized_seeds
    )
    assigned = np.empty((chain_count, len(names)), dtype=int)
    for parameter_index, _name in enumerate(names):
        assigned[:, parameter_index] = plan_rng.permutation(chain_count)

    accepted: list[dict[str, float] | None] = [None] * chain_count
    for _attempt in range(config.max_attempts):
        for chain_index, chain_rng in enumerate(chain_rngs):
            if accepted[chain_index] is not None:
                continue
            candidate = {
                name: _bounded_marginal_quantile(
                    prior,
                    name,
                    float(lower[parameter_index]),
                    float(upper[parameter_index]),
                    (
                        float(assigned[chain_index, parameter_index])
                        + float(chain_rng.random())
                    )
                    / chain_count,
                )
                for parameter_index, name in enumerate(names)
            }
            if _has_prior_support(lpm, prior, names, candidate):
                accepted[chain_index] = candidate
        if all(state is not None for state in accepted):
            return [state for state in accepted if state is not None]

    unsupported = [index + 1 for index, state in enumerate(accepted) if state is None]
    raise ValueError(
        "bounds_stratified quantile initialization produced zero-density states "
        f"for chains {unsupported} after {config.max_attempts} attempts; check "
        "prior numerical support"
    )


def build_initial_states(
    lpm: Any,
    prior: Any,
    config: MHInitializationConfig,
    chain_count: int,
    seeds: Sequence[int],
) -> tuple[dict[str, float], ...]:
    """Build reproducible initial parameter mappings from disjoint RNG streams.

    Parameters
    ----------
    lpm
        Model exposing canonical names, current values, and physical bounds.
    prior
        Loaded :class:`~pyages.calibration.methods.mh.prior.Prior`, required
        only by ``prior_sample`` and ``prior_map``.
    config
        Initialization strategy and its controls.
    chain_count
        Number of states to construct; must be at least two.
    seeds
        One distinct non-negative initialization seed per chain.

    Returns
    -------
    tuple[dict[str, float], ...]
        Fresh dictionaries in canonical parameter order. Neither ``lpm`` nor
        ``prior`` is modified.
    """
    if not isinstance(config, MHInitializationConfig):
        raise TypeError("config must be an MHInitializationConfig")
    if (
        isinstance(chain_count, bool)
        or not isinstance(chain_count, int)
        or chain_count < 2
    ):
        raise ValueError("chain_count must be an integer greater than or equal to two")
    normalized_seeds = _validated_seeds(seeds, chain_count)
    names = _parameter_names(lpm)
    lower, upper = _parameter_bounds(lpm, names)

    if config.strategy == "explicit":
        starts = config.explicit_starts
        if starts is None:
            raise AssertionError("validated explicit initialization has no starts")
        if len(starts) != chain_count:
            raise ValueError(
                "explicit_starts must contain exactly one state per chain "
                f"(expected {chain_count}, got {len(starts)})"
            )
        candidates = [dict(start) for start in starts]
    elif config.strategy == "model_default":
        default = _model_default_state(lpm, names)
        candidates = [dict(default) for _ in range(chain_count)]
    elif config.strategy == "prior_map":
        prior_map = _prior_state(prior, names, lower, upper, None, sample=False)
        candidates = [dict(prior_map) for _ in range(chain_count)]
    elif config.strategy == "prior_sample":
        candidates = [
            _prior_state(
                prior,
                names,
                lower,
                upper,
                np.random.default_rng(seed),
                sample=True,
            )
            for seed in normalized_seeds
        ]
    else:
        candidates = _bounds_stratified_states(
            lpm,
            prior,
            config,
            names,
            lower,
            upper,
            normalized_seeds,
            chain_count,
        )

    validated = tuple(
        _validate_state(candidate, names, lower, upper) for candidate in candidates
    )
    unsupported = [
        index + 1
        for index, state in enumerate(validated)
        if not _has_prior_support(lpm, prior, names, state)
    ]
    if unsupported:
        raise ValueError(
            "initial states have zero prior density for chains "
            f"{unsupported}; choose a prior-supported initialization"
        )
    return validated


__all__ = ["build_initial_states"]
