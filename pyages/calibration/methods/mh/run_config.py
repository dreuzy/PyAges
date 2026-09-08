# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file checks settings shared by an MH run containing one or more chains.

"""Define configuration objects shared by any managed MH run.

These objects describe how many chains to run, how to choose their starting
states, whether to run a pilot stage, and which diagnostic limits must pass.
The module also turns one run seed into separate reproducible seeds for
initialization, pilot chains, and production chains.
"""

from __future__ import annotations

import math
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

from pyages.calibration.methods.mh._immutable import FrozenMapping
from pyages.config.sampling_schedule import strict_retained_sample_count

INITIALIZATION_STRATEGIES = frozenset(
    {
        "prior_sample",
        "bounds_stratified",
        "explicit",
    }
)


def _is_positive_integer(value: object) -> bool:
    """Return whether ``value`` is an integer greater than zero."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _frozen_explicit_start(start: Mapping[str, float]) -> FrozenMapping[float]:
    """Validate and freeze one explicit finite parameter state."""
    if not isinstance(start, Mapping) or not start:
        raise ValueError("explicit starts must be non-empty parameter mappings")
    copied: dict[str, float] = {}
    for name, raw_value in start.items():
        if not isinstance(name, str) or not name:
            raise ValueError("explicit start names must be non-empty strings")
        if isinstance(raw_value, (bool, np.bool_)):
            raise ValueError("explicit start values must be finite numbers")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("explicit start values must be finite numbers") from exc
        if not math.isfinite(value):
            raise ValueError("explicit start values must be finite numbers")
        copied[name] = value
    return FrozenMapping(copied)


@dataclass(frozen=True)
class MHInitializationConfig:
    """Controls for constructing independent, bounded chain starts.

    ``prior_sample`` draws each start independently from the configured prior
    conditioned on the LPM calibration ranges.
    ``bounds_stratified`` uses a Latin hypercube over the calibration ranges,
    or over effective marginal prior mass when a prior is active.

    ``explicit`` consumes ``explicit_starts`` in chain order.

    Explicit mappings are copied and made read-only at construction.
    """

    strategy: str = "bounds_stratified"
    explicit_starts: tuple[Mapping[str, float], ...] | None = None
    max_attempts: int = 100

    def __post_init__(self) -> None:
        """Validate the initialization controls and freeze explicit starts."""
        if self.strategy not in INITIALIZATION_STRATEGIES:
            choices = ", ".join(sorted(INITIALIZATION_STRATEGIES))
            raise ValueError(
                f"Unknown initialization strategy: {self.strategy!r}; {choices}"
            )
        if not _is_positive_integer(self.max_attempts):
            raise ValueError("max_attempts must be a positive integer")
        if self.explicit_starts is not None:
            try:
                raw_starts = tuple(self.explicit_starts)
            except TypeError as exc:
                raise ValueError(
                    "explicit_starts must contain parameter mappings"
                ) from exc
            starts = tuple(_frozen_explicit_start(start) for start in raw_starts)
            object.__setattr__(self, "explicit_starts", starts)
        if self.strategy == "explicit" and self.explicit_starts is None:
            raise ValueError("explicit initialization requires explicit_starts")
        if self.strategy != "explicit" and self.explicit_starts is not None:
            raise ValueError(
                "explicit_starts are accepted only with strategy='explicit'"
            )


@dataclass(frozen=True)
class MHPilotConfig:
    """Controls for pilot chains used to learn a fixed proposal covariance.

    ``nsteps`` and fractional ``burn_in`` define pilot transitions retained with
    no thinning.

    Each chain is centered separately before estimating the shared
    native-coordinate covariance. ``relative_ridge`` regularizes that
    covariance against singularity. A ``None`` proposal multiplier selects
    ``2.38 / sqrt(dimension)``.

    Pilot draws never enter the posterior. They are persisted only when
    ``save_samples`` is true.
    """

    enabled: bool = False
    nsteps: int = 2_000
    burn_in: float = 0.5
    relative_ridge: float = 1.0e-6
    proposal_multiplier: float | None = None
    save_samples: bool = False

    def __post_init__(self) -> None:
        """Reject unusable pilot lengths and covariance controls."""
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if not _is_positive_integer(self.nsteps):
            raise ValueError("nsteps must be a positive integer")
        if (
            isinstance(self.burn_in, (bool, np.bool_))
            or not math.isfinite(self.burn_in)
            or not 0.0 <= self.burn_in < 1.0
        ):
            raise ValueError("burn_in must be finite and in [0, 1)")
        retained_count = strict_retained_sample_count(self.nsteps, self.burn_in, 1)
        if self.enabled and retained_count < 2:
            raise ValueError(
                "pilot nsteps and burn_in must retain at least two covariance draws"
            )
        if (
            isinstance(self.relative_ridge, bool)
            or not math.isfinite(self.relative_ridge)
            or self.relative_ridge < 0.0
        ):
            raise ValueError("relative_ridge must be finite and non-negative")
        if self.proposal_multiplier is not None and (
            isinstance(self.proposal_multiplier, bool)
            or not math.isfinite(self.proposal_multiplier)
            or self.proposal_multiplier <= 0.0
        ):
            raise ValueError("proposal_multiplier must be finite and positive")
        if not isinstance(self.save_samples, bool):
            raise ValueError("save_samples must be a boolean")


@dataclass(frozen=True)
class MHDiagnosticsConfig:
    """Qualification thresholds applied to production-chain diagnostics.

    A quantity qualifies only when split rank-normalized R-hat is strictly less
    than ``max_rhat``, bulk and tail ESS are at least their respective minima,
    and its mean MCSE is finite.

    ``require_convergence`` controls whether an unqualified ensemble may be
    pooled for explicitly exploratory output. It does not weaken calculation
    or recording of the diagnostics themselves.
    """

    max_rhat: float = 1.01
    min_bulk_ess: float = 300.0
    min_tail_ess: float = 300.0
    require_convergence: bool = True

    def __post_init__(self) -> None:
        """Validate finite and statistically meaningful thresholds."""
        if (
            isinstance(self.max_rhat, bool)
            or not math.isfinite(self.max_rhat)
            or self.max_rhat <= 1.0
        ):
            raise ValueError("max_rhat must be finite and greater than one")
        for name in ("min_bulk_ess", "min_tail_ess"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not isinstance(self.require_convergence, bool):
            raise ValueError("require_convergence must be a boolean")


@dataclass(frozen=True)
class MHRunConfig:
    """Configuration shared by one reproducible run of one or more MH chains.

    Set ``seed=None`` to realize a cryptographically generated seed on
    this immutable object. The default is the deterministic seed ``12345``.

    In both cases, the realized seed is stored so that every run can record and
    replay its random streams.
    """

    chains: int = 1
    seed: int | None = 12_345
    initialization: MHInitializationConfig = field(
        default_factory=MHInitializationConfig
    )
    pilot: MHPilotConfig = field(default_factory=MHPilotConfig)
    diagnostics: MHDiagnosticsConfig = field(default_factory=MHDiagnosticsConfig)

    def __post_init__(self) -> None:
        """Validate the chain count and realize an omitted run seed."""
        if (
            isinstance(self.chains, bool)
            or not isinstance(self.chains, int)
            or self.chains < 1
        ):
            raise ValueError("chains must be a positive integer")
        seed = self.seed
        if seed is None:
            seed = secrets.randbits(64)
            object.__setattr__(self, "seed", seed)
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("seed must be a non-negative integer or None")
        if not isinstance(self.initialization, MHInitializationConfig):
            raise ValueError("initialization must be an MHInitializationConfig")
        if not isinstance(self.pilot, MHPilotConfig):
            raise ValueError("pilot must be an MHPilotConfig")
        if not isinstance(self.diagnostics, MHDiagnosticsConfig):
            raise ValueError("diagnostics must be an MHDiagnosticsConfig")


@dataclass(frozen=True)
class MHSeedPlan:
    """Concrete independent seeds for initialization, pilot, and production."""

    seed: int
    initialization_seeds: tuple[int, ...]
    pilot_seeds: tuple[int, ...]
    production_seeds: tuple[int, ...]

    def __post_init__(self) -> None:
        """Freeze and validate complete, non-overlapping phase streams."""
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or self.seed < 0
        ):
            raise ValueError("seed must be a non-negative integer")
        phase_seeds: list[tuple[int, ...]] = []
        for name in (
            "initialization_seeds",
            "pilot_seeds",
            "production_seeds",
        ):
            try:
                values = tuple(getattr(self, name))
            except TypeError as exc:
                raise ValueError(f"{name} must be an iterable of seeds") from exc
            if not values or any(
                isinstance(seed, (bool, np.bool_))
                or not isinstance(seed, (int, np.integer))
                or int(seed) < 0
                for seed in values
            ):
                raise ValueError(f"{name} must contain non-negative integer seeds")
            normalized = tuple(int(seed) for seed in values)
            object.__setattr__(self, name, normalized)
            phase_seeds.append(normalized)
        if len({len(values) for values in phase_seeds}) != 1:
            raise ValueError("seed phases must contain the same number of chains")
        flattened = tuple(seed for values in phase_seeds for seed in values)
        if len(set(flattened)) != len(flattened):
            raise ValueError("seed phases must contain distinct streams")

    @property
    def chain_count(self) -> int:
        """Return the number of chains represented by each phase."""
        return len(self.production_seeds)


def _child_seeds(parent: np.random.SeedSequence, count: int) -> tuple[int, ...]:
    """Materialize deterministic unsigned 64-bit seeds from child streams."""
    return tuple(
        int(child.generate_state(1, dtype=np.uint64)[0])
        for child in parent.spawn(count)
    )


def build_seed_plan(config: MHRunConfig) -> MHSeedPlan:
    """Build distinct phase and per-chain streams from ``config.seed``.

    The hierarchy is stable: adding random draws inside initialization or a
    pilot does not advance or otherwise alter any production-chain stream. The
    first production stream is also identical for ``chains=1`` and
    ``chains>1``; changing only the chain count therefore adds streams without
    changing the first chain.
    """
    if not isinstance(config, MHRunConfig):
        raise TypeError("config must be an MHRunConfig")
    if config.seed is None:  # defensive; ``__post_init__`` realizes it
        raise AssertionError("validated run config has no seed")

    root = np.random.SeedSequence(config.seed)
    initialization_root, pilot_root, production_root = root.spawn(3)
    production_seeds = _child_seeds(production_root, config.chains)

    plan = MHSeedPlan(
        seed=config.seed,
        initialization_seeds=_child_seeds(initialization_root, config.chains),
        pilot_seeds=_child_seeds(pilot_root, config.chains),
        production_seeds=production_seeds,
    )

    all_seeds = plan.initialization_seeds + plan.pilot_seeds + plan.production_seeds
    if len(set(all_seeds)) != len(all_seeds):  # practically impossible
        raise RuntimeError("SeedSequence generated duplicate chain streams")
    return plan


__all__ = [
    "MHDiagnosticsConfig",
    "MHRunConfig",
    "MHInitializationConfig",
    "MHPilotConfig",
    "MHSeedPlan",
    "build_seed_plan",
]
