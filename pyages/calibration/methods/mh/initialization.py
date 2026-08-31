# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Pure construction of reproducible initial states for MH chain ensembles."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Protocol

import numpy as np

from pyages.calibration.methods.mh.ensemble_config import MHInitializationConfig


class _LpmInitializationView(Protocol):
    """Canonical read-only LPM interface required for initialization."""

    def get_param_names(self) -> Sequence[str]:
        """Return parameter names in canonical calibration order."""
        ...

    def get_parameters_to_array(self) -> Sequence[float]:
        """Return current values in canonical calibration order."""
        ...

    def get_p_min(self, name: str) -> float:
        """Return the physical lower bound for ``name``."""
        ...

    def get_p_max(self, name: str) -> float:
        """Return the physical upper bound for ``name``."""
        ...


class _MarginalPrior(Protocol):
    """Prior operations consumed by initialization without storage coupling."""

    option: bool

    def require_marginals(self, names: Sequence[str]) -> None:
        """Require loaded definitions for all ``names``."""
        ...

    def bounded_quantile(
        self,
        name: str,
        minimum: float,
        maximum: float,
        probability: float,
    ) -> float:
        """Invert a marginal after restriction to physical bounds."""
        ...

    def bounded_mode(self, name: str, minimum: float, maximum: float) -> float:
        """Return a marginal mode restricted to physical bounds."""
        ...

    def contains(self, name: str, value: float) -> bool:
        """Return whether ``value`` has positive marginal density."""
        ...


def _parameter_names(lpm: _LpmInitializationView) -> tuple[str, ...]:
    """Return the model's canonical parameter order."""
    try:
        names = tuple(lpm.get_param_names())
    except AttributeError as exc:
        raise TypeError("lpm must expose get_param_names()") from exc
    except TypeError as exc:
        raise ValueError("lpm parameter names must be an iterable") from exc
    if not names or any(not isinstance(name, str) for name in names):
        raise ValueError("lpm must expose at least one named parameter")
    if len(set(names)) != len(names):
        raise ValueError("lpm parameter names must be unique")
    return names


def _parameter_bounds(
    lpm: _LpmInitializationView,
    names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
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
    state: Mapping[str, object],
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


def _require_prior(
    prior: _MarginalPrior | None,
    names: Sequence[str],
) -> _MarginalPrior:
    """Return an active prior after validating its marginal coverage."""
    if prior is None or prior.option is not True:
        raise ValueError("prior initialization requires an enabled prior")
    prior.require_marginals(names)
    return prior


def _bounded_marginal_quantile(
    prior: _MarginalPrior | None,
    name: str,
    minimum: float,
    maximum: float,
    probability: float,
) -> float:
    """Map probability mass to one physical or active-prior marginal."""
    if prior is None or prior.option is not True:
        return minimum + probability * (maximum - minimum)
    return prior.bounded_quantile(
        name,
        minimum,
        maximum,
        probability,
    )


def _prior_state(
    prior: _MarginalPrior | None,
    names: Sequence[str],
    lower: np.ndarray,
    upper: np.ndarray,
    rng: np.random.Generator | None,
    *,
    sample: bool,
) -> dict[str, float]:
    """Construct one sampled or MAP-like state from an already loaded prior."""
    active_prior = _require_prior(prior, names)
    state: dict[str, float] = {}
    for index, name in enumerate(names):
        minimum, maximum = float(lower[index]), float(upper[index])
        if sample:
            if rng is None:
                raise AssertionError("sampled initialization requires an RNG")
            value = active_prior.bounded_quantile(
                name,
                minimum,
                maximum,
                float(rng.random()),
            )
        else:
            value = active_prior.bounded_mode(name, minimum, maximum)
        state[name] = value
    return state


def _model_default_state(
    lpm: _LpmInitializationView,
    names: Sequence[str],
) -> dict[str, float]:
    """Copy the current model parameters without mutating the model."""
    try:
        values = lpm.get_parameters_to_array()
    except AttributeError as exc:
        raise TypeError("lpm must expose get_parameters_to_array()") from exc
    if len(values) != len(names):
        raise ValueError("lpm default parameter count does not match its names")
    return dict(zip(names, values, strict=True))


def _has_prior_support(
    prior: _MarginalPrior | None,
    names: Sequence[str],
    state: Mapping[str, float],
) -> bool:
    """Return whether one bounded state belongs to the active prior support."""
    if prior is None or prior.option is not True:
        return True
    active_prior = _require_prior(prior, names)
    return all(active_prior.contains(name, state[name]) for name in names)


def _bounds_stratified_states(
    prior: _MarginalPrior | None,
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
    if prior is not None and prior.option is True:
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
            if _has_prior_support(prior, names, candidate):
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
    lpm: _LpmInitializationView,
    prior: _MarginalPrior | None,
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
        if not _has_prior_support(prior, names, state)
    ]
    if unsupported:
        raise ValueError(
            "initial states have zero prior density for chains "
            f"{unsupported}; choose a prior-supported initialization"
        )
    return validated


__all__ = ["build_initial_states"]
