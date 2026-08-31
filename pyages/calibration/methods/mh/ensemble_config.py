# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validated configuration and random streams for MH chain ensembles."""

from __future__ import annotations

import math
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

INITIALIZATION_STRATEGIES = frozenset(
    {
        "prior_sample",
        "bounds_stratified",
        "explicit",
        "model_default",
        "prior_map",
    }
)


def _is_positive_integer(value: object) -> bool:
    """Return whether ``value`` is an integer greater than zero."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


@dataclass(frozen=True)
class MHInitializationConfig:
    """Controls for constructing independent, bounded chain starts.

    ``prior_sample`` draws each start independently from the configured prior.
    ``bounds_stratified`` uses a Latin hypercube over the physical LPM bounds,
    or over effective marginal prior mass when a prior is active.
    ``explicit`` consumes ``explicit_starts`` in chain order, while
    ``model_default`` and ``prior_map`` preserve deterministic compatibility
    modes. Explicit mappings are copied and made read-only at construction.
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
                starts = tuple(
                    MappingProxyType(dict(start)) for start in self.explicit_starts
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "explicit_starts must contain parameter mappings"
                ) from exc
            object.__setattr__(self, "explicit_starts", starts)
        if self.strategy == "explicit" and self.explicit_starts is None:
            raise ValueError("explicit initialization requires explicit_starts")
        if self.strategy != "explicit" and self.explicit_starts is not None:
            raise ValueError(
                "explicit_starts are accepted only with strategy='explicit'"
            )


@dataclass(frozen=True)
class MHPilotConfig:
    """Controls for pilot chains used to learn a fixed proposal covariance."""

    enabled: bool = True
    nstep: int = 2_000
    burn_in: float = 0.5
    covariance_mode: str = "pooled_within_chain"
    relative_ridge: float = 1.0e-6
    proposal_multiplier: float | None = None
    save_samples: bool = False

    def __post_init__(self) -> None:
        """Reject unusable pilot lengths and covariance controls."""
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if not _is_positive_integer(self.nstep):
            raise ValueError("nstep must be a positive integer")
        if not math.isfinite(self.burn_in) or not 0.0 <= self.burn_in < 1.0:
            raise ValueError("burn_in must be finite and in [0, 1)")
        retained_count = self.nstep - math.floor(self.burn_in * self.nstep) - 1
        if self.enabled and retained_count < 2:
            raise ValueError(
                "pilot nstep and burn_in must retain at least two covariance draws"
            )
        if self.covariance_mode != "pooled_within_chain":
            raise ValueError("covariance_mode must be 'pooled_within_chain'")
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
    """Qualification thresholds applied to production-chain diagnostics."""

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
class MHEnsembleConfig:
    """Configuration shared by one reproducible ensemble of MH chains.

    Set ``master_seed=None`` to realize a cryptographically generated seed on
    this immutable object. The default is the deterministic seed ``12345``.
    Consequently every realized run can record and replay the random streams.
    """

    chains: int = 4
    master_seed: int | None = 12_345
    initialization: MHInitializationConfig = field(
        default_factory=MHInitializationConfig
    )
    pilot: MHPilotConfig = field(default_factory=MHPilotConfig)
    diagnostics: MHDiagnosticsConfig = field(default_factory=MHDiagnosticsConfig)

    def __post_init__(self) -> None:
        """Validate the chain count and realize an omitted master seed."""
        if (
            isinstance(self.chains, bool)
            or not isinstance(self.chains, int)
            or self.chains < 2
        ):
            raise ValueError("chains must be an integer greater than or equal to two")
        master_seed = self.master_seed
        if master_seed is None:
            master_seed = secrets.randbits(64)
            object.__setattr__(self, "master_seed", master_seed)
        if (
            isinstance(master_seed, bool)
            or not isinstance(master_seed, int)
            or master_seed < 0
        ):
            raise ValueError("master_seed must be a non-negative integer or None")
        if not isinstance(self.initialization, MHInitializationConfig):
            raise ValueError("initialization must be an MHInitializationConfig")
        if not isinstance(self.pilot, MHPilotConfig):
            raise ValueError("pilot must be an MHPilotConfig")
        if not isinstance(self.diagnostics, MHDiagnosticsConfig):
            raise ValueError("diagnostics must be an MHDiagnosticsConfig")


@dataclass(frozen=True)
class MHSeedPlan:
    """Concrete independent seeds for initialization, pilot, and production."""

    master_seed: int
    initialization_seeds: tuple[int, ...]
    pilot_seeds: tuple[int, ...]
    production_seeds: tuple[int, ...]

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


def build_seed_plan(config: MHEnsembleConfig) -> MHSeedPlan:
    """Build distinct phase and per-chain streams from ``config.master_seed``.

    The hierarchy is stable: adding random draws inside initialization or a
    pilot does not advance or otherwise alter any production-chain stream.
    """
    if not isinstance(config, MHEnsembleConfig):
        raise TypeError("config must be an MHEnsembleConfig")
    if config.master_seed is None:  # defensive; ``__post_init__`` realizes it
        raise AssertionError("validated ensemble config has no master seed")
    root = np.random.SeedSequence(config.master_seed)
    initialization_root, pilot_root, production_root = root.spawn(3)
    plan = MHSeedPlan(
        master_seed=config.master_seed,
        initialization_seeds=_child_seeds(initialization_root, config.chains),
        pilot_seeds=_child_seeds(pilot_root, config.chains),
        production_seeds=_child_seeds(production_root, config.chains),
    )
    all_seeds = plan.initialization_seeds + plan.pilot_seeds + plan.production_seeds
    if len(set(all_seeds)) != len(all_seeds):  # practically impossible
        raise RuntimeError("SeedSequence generated duplicate chain streams")
    return plan


__all__ = [
    "MHDiagnosticsConfig",
    "MHEnsembleConfig",
    "MHInitializationConfig",
    "MHPilotConfig",
    "MHSeedPlan",
    "build_seed_plan",
]
