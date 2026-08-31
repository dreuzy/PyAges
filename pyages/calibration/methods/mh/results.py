# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structured results for pilot, production, and diagnostic MCMC stages."""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from pyages.calibration.methods.mh.ensemble_config import MHSeedPlan
from pyages.lpm.samples.table import LpmSampleTable

QUALIFIED = "qualified"
NOT_QUALIFIED = "not_qualified"
DIAGNOSTICS_UNAVAILABLE = "diagnostics_unavailable"
QUALIFICATION_STATUSES = frozenset({QUALIFIED, NOT_QUALIFIED, DIAGNOSTICS_UNAVAILABLE})
QualificationStatus = Literal["qualified", "not_qualified", "diagnostics_unavailable"]


def _readonly_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a detached read-only copy of resolved run metadata."""
    if not isinstance(metadata, Mapping):
        raise TypeError("resolved_metadata must be a mapping")
    copied = deepcopy(dict(metadata))
    if any(not isinstance(name, str) or not name for name in copied):
        raise ValueError("resolved metadata names must be non-empty strings")
    if any(not isinstance(value, (str, int, float, bool)) for value in copied.values()):
        raise ValueError("resolved metadata values must be scalar")
    return MappingProxyType(copied)


def _copied_finite_state(state: dict[str, float]) -> dict[str, float]:
    """Return one validated independent parameter-state mapping."""
    if not state:
        raise ValueError("parameter states must not be empty")
    copied = {name: float(value) for name, value in state.items()}
    if not all(isinstance(name, str) and name for name in copied):
        raise ValueError("parameter names must be non-empty strings")
    if not all(math.isfinite(value) for value in copied.values()):
        raise ValueError("parameter states must contain only finite values")
    return copied


def _validated_pilot_states(
    states: tuple[dict[str, float], ...],
) -> tuple[tuple[dict[str, float], ...], tuple[str, ...]]:
    """Return copied pilot states and their shared ordered parameter names."""
    copied = tuple(_copied_finite_state(state) for state in states)
    if not copied:
        raise ValueError("final_states must contain at least one pilot state")
    parameter_names = tuple(copied[0])
    if any(tuple(state) != parameter_names for state in copied[1:]):
        raise ValueError("pilot states must use the same ordered parameters")
    return copied, parameter_names


def _readonly_pilot_covariance(
    covariance: np.ndarray, parameter_count: int
) -> np.ndarray:
    """Return a validated read-only proposal covariance copy."""
    copied = np.array(covariance, dtype=float, copy=True)
    if copied.shape != (parameter_count, parameter_count):
        raise ValueError("pilot covariance dimension must match parameter states")
    if not np.all(np.isfinite(copied)):
        raise ValueError("pilot covariance must be finite")
    if not np.allclose(copied, copied.T, rtol=1.0e-12, atol=1.0e-12):
        raise ValueError("pilot covariance must be symmetric")
    if np.any(np.linalg.eigvalsh(copied) <= 0.0):
        raise ValueError("pilot covariance must be positive definite")
    copied.setflags(write=False)
    return copied


def _validated_acceptance_rates(
    rates: tuple[float, ...], chain_count: int
) -> tuple[float, ...]:
    """Return exactly one finite acceptance probability per pilot chain."""
    copied = tuple(float(rate) for rate in rates)
    if len(copied) != chain_count or any(
        not math.isfinite(rate) or not 0.0 <= rate <= 1.0 for rate in copied
    ):
        raise ValueError(
            "acceptance_rates must contain one finite probability per chain"
        )
    return copied


def _validated_retained_counts(
    counts: tuple[int, ...], chain_count: int
) -> tuple[int, ...]:
    """Return exactly one usable retained-draw count per pilot chain."""
    copied = tuple(counts)
    if len(copied) != chain_count or any(
        isinstance(count, bool) or not isinstance(count, (int, np.integer)) or count < 2
        for count in copied
    ):
        raise ValueError(
            "retained_counts must contain one integer of at least two per chain"
        )
    return tuple(int(count) for count in copied)


def _validated_runtimes(
    runtimes: tuple[float, ...] | None,
    chain_count: int,
) -> tuple[float, ...] | None:
    """Return optional finite non-negative runtime values per pilot chain."""
    if runtimes is None:
        return None
    copied = tuple(float(runtime) for runtime in runtimes)
    if len(copied) != chain_count or any(
        not math.isfinite(runtime) or runtime < 0.0 for runtime in copied
    ):
        raise ValueError(
            "runtime_seconds must contain one finite non-negative value per chain"
        )
    return copied


def _readonly_pilot_samples(
    samples: tuple[np.ndarray, ...] | None,
    counts: tuple[int, ...],
    parameter_count: int,
) -> tuple[np.ndarray, ...] | None:
    """Return validated read-only pilot-sample copies when requested."""
    if samples is None:
        return None
    if len(samples) != len(counts):
        raise ValueError("samples must contain one matrix per pilot chain")
    copied = []
    for index, chain in enumerate(samples):
        values = np.array(chain, dtype=float, copy=True)
        if values.shape != (counts[index], parameter_count):
            raise ValueError(
                "saved pilot samples must match retained counts and parameters"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("saved pilot samples must be finite")
        values.setflags(write=False)
        copied.append(values)
    return tuple(copied)


@dataclass(frozen=True)
class MHPilotResult:
    """Results retained after learning one common proposal covariance.

    ``initial_states`` records the dispersed pre-pilot starts and
    ``runtime_seconds`` records each pilot's cost. ``samples`` is optional so
    production runs need not retain pilot draws. When present, numerical
    arrays are copied and marked read-only.
    """

    final_states: tuple[dict[str, float], ...]
    covariance: np.ndarray
    proposal_multiplier: float
    acceptance_rates: tuple[float, ...]
    retained_counts: tuple[int, ...]
    samples: tuple[np.ndarray, ...] | None = None
    initial_states: tuple[dict[str, float], ...] | None = None
    runtime_seconds: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        """Validate dimensions and detach mutable numerical inputs."""
        states, parameter_names = _validated_pilot_states(self.final_states)
        covariance = _readonly_pilot_covariance(self.covariance, len(parameter_names))

        if (
            isinstance(self.proposal_multiplier, bool)
            or not math.isfinite(self.proposal_multiplier)
            or self.proposal_multiplier <= 0.0
        ):
            raise ValueError("proposal_multiplier must be finite and positive")

        rates = _validated_acceptance_rates(self.acceptance_rates, len(states))
        counts = _validated_retained_counts(self.retained_counts, len(states))
        saved_samples = _readonly_pilot_samples(
            self.samples, counts, len(parameter_names)
        )
        runtimes = _validated_runtimes(self.runtime_seconds, len(states))
        initial_states = None
        if self.initial_states is not None:
            initial_states, initial_names = _validated_pilot_states(self.initial_states)
            if len(initial_states) != len(states):
                raise ValueError(
                    "initial_states must contain one state per pilot chain"
                )
            if initial_names != parameter_names:
                raise ValueError(
                    "initial_states must use the pilot covariance parameters"
                )

        object.__setattr__(self, "final_states", states)
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "proposal_multiplier", float(self.proposal_multiplier))
        object.__setattr__(self, "acceptance_rates", rates)
        object.__setattr__(self, "retained_counts", counts)
        object.__setattr__(self, "samples", saved_samples)
        object.__setattr__(self, "initial_states", initial_states)
        object.__setattr__(self, "runtime_seconds", runtimes)


@dataclass(frozen=True)
class MHChainResult:
    """Samples and provenance produced by one independent production chain."""

    chain_id: int
    seed: int
    initial_params: dict[str, float]
    samples: LpmSampleTable
    acceptance_rate: float
    runtime_seconds: float

    def __post_init__(self) -> None:
        """Validate scalar provenance while preserving the individual table."""
        if (
            isinstance(self.chain_id, bool)
            or not isinstance(self.chain_id, int)
            or self.chain_id <= 0
        ):
            raise ValueError("chain_id must be a positive integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if not isinstance(self.samples, LpmSampleTable):
            raise TypeError("samples must be an LpmSampleTable")
        self.samples.validate()
        if (
            not math.isfinite(self.acceptance_rate)
            or not 0.0 <= self.acceptance_rate <= 1.0
        ):
            raise ValueError("acceptance_rate must be a finite probability")
        if not math.isfinite(self.runtime_seconds) or self.runtime_seconds < 0.0:
            raise ValueError("runtime_seconds must be finite and non-negative")
        object.__setattr__(
            self, "initial_params", _copied_finite_state(self.initial_params)
        )
        object.__setattr__(self, "acceptance_rate", float(self.acceptance_rate))
        object.__setattr__(self, "runtime_seconds", float(self.runtime_seconds))


@dataclass(frozen=True)
class MHParameterDiagnostics:
    """Convergence metrics for one sampled or derived posterior quantity.

    ``included_in_qualification`` is false only for structurally constant
    derived quantities whose R-hat and ESS are undefined. Native sampled
    parameters always remain part of the convergence gate.
    """

    parameter: str
    rhat: float
    bulk_ess: float
    tail_ess: float
    mcse_mean: float
    posterior_sd: float
    qualified: bool
    included_in_qualification: bool = True

    def __post_init__(self) -> None:
        """Normalize numeric scalar types without hiding unavailable metrics."""
        if not isinstance(self.parameter, str) or not self.parameter:
            raise ValueError("parameter must be a non-empty string")
        if not isinstance(self.qualified, bool):
            raise ValueError("qualified must be a boolean")
        if not isinstance(self.included_in_qualification, bool):
            raise ValueError("included_in_qualification must be a boolean")
        for name in ("rhat", "bulk_ess", "tail_ess", "mcse_mean", "posterior_sd"):
            object.__setattr__(self, name, float(getattr(self, name)))


def _validate_ensemble_chains(chains: tuple[MHChainResult, ...]) -> None:
    """Validate production-chain types and canonical identifiers."""
    if not chains:
        raise ValueError("chains must contain at least one production chain")
    if any(not isinstance(chain, MHChainResult) for chain in chains):
        raise TypeError("chains must contain only MHChainResult objects")
    chain_ids = tuple(chain.chain_id for chain in chains)
    expected_ids = tuple(range(1, len(chains) + 1))
    if chain_ids != expected_ids:
        raise ValueError(
            "production chain identifiers must be ordered exactly from 1 to N"
        )


def _validate_seed_plan(
    seed_plan: MHSeedPlan,
    chains: tuple[MHChainResult, ...],
) -> None:
    """Require complete phase streams coherent with recorded production chains."""
    if not isinstance(seed_plan, MHSeedPlan):
        raise TypeError("seed_plan must be an MHSeedPlan")
    if isinstance(seed_plan.master_seed, bool) or not isinstance(
        seed_plan.master_seed, int
    ):
        raise ValueError("seed_plan.master_seed must be an integer")
    chain_count = len(chains)
    if not (
        len(seed_plan.initialization_seeds)
        == len(seed_plan.pilot_seeds)
        == len(seed_plan.production_seeds)
        == chain_count
    ):
        raise ValueError("seed_plan must contain one seed per chain and phase")
    all_seeds = (
        seed_plan.initialization_seeds
        + seed_plan.pilot_seeds
        + seed_plan.production_seeds
    )
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in all_seeds):
        raise ValueError("seed_plan phase seeds must be integers")
    if len(set(all_seeds)) != len(all_seeds):
        raise ValueError("seed_plan phase seeds must be distinct")
    recorded_seeds = tuple(chain.seed for chain in chains)
    if recorded_seeds != seed_plan.production_seeds:
        raise ValueError("production chain seeds must match seed_plan")


def _validate_target_signature(version: int, sha256: str) -> None:
    """Validate the compact versioned scientific-target provenance."""
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise ValueError("target_signature_version must be a positive integer")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or sha256 != sha256.lower()
        or any(character not in "0123456789abcdef" for character in sha256)
    ):
        raise ValueError("target_sha256 must be a lowercase SHA-256 hexadecimal digest")


def _validate_diagnostic_status(
    diagnostics: tuple[MHParameterDiagnostics, ...],
    qualification_status: QualificationStatus,
    message: str | None,
) -> None:
    """Validate consistency between diagnostics, status, and error message."""
    if qualification_status not in QUALIFICATION_STATUSES:
        raise ValueError(
            f"qualification_status must be one of {sorted(QUALIFICATION_STATUSES)}"
        )
    if message is not None and (not isinstance(message, str) or not message.strip()):
        raise ValueError("diagnostics_message must be a non-empty string or None")
    if qualification_status == DIAGNOSTICS_UNAVAILABLE:
        if diagnostics:
            raise ValueError(
                "diagnostics_unavailable ensembles must not contain partial diagnostics"
            )
        if message is None:
            raise ValueError(
                "diagnostics_unavailable ensembles require diagnostics_message"
            )
        return
    if message is not None:
        raise ValueError(
            "diagnostics_message is accepted only when diagnostics are unavailable"
        )
    if not diagnostics:
        raise ValueError("qualified and non-qualified ensembles need diagnostics")
    gating = tuple(item for item in diagnostics if item.included_in_qualification)
    if qualification_status == QUALIFIED and (
        not gating or not all(item.qualified for item in gating)
    ):
        raise ValueError("qualified ensembles require qualified diagnostics")
    if qualification_status == NOT_QUALIFIED and (
        not gating or all(item.qualified for item in gating)
    ):
        raise ValueError("not_qualified ensembles require a failed gating diagnostic")


@dataclass(frozen=True)
class MHEnsembleResult:
    """Separate chains, diagnostics, status, and file-backed input snapshots.

    ``resolved_metadata`` contains detached proposal/prior values captured by
    the samplers immediately after preparation and before their transition
    loops.  Keeping this snapshot on the result prevents later input-file
    changes from altering the provenance eventually serialized for the run.
    """

    chains: tuple[MHChainResult, ...]
    pilot: MHPilotResult | None
    diagnostics: tuple[MHParameterDiagnostics, ...]
    qualification_status: QualificationStatus
    seed_plan: MHSeedPlan
    target_signature_version: int
    target_sha256: str
    diagnostics_message: str | None = None
    resolved_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate ensemble identity and detach caller-owned sequences."""
        chains = tuple(self.chains)
        diagnostics = tuple(self.diagnostics)
        _validate_ensemble_chains(chains)
        _validate_seed_plan(self.seed_plan, chains)
        _validate_target_signature(
            self.target_signature_version,
            self.target_sha256,
        )
        if any(
            not isinstance(diagnostic, MHParameterDiagnostics)
            for diagnostic in diagnostics
        ):
            raise TypeError(
                "diagnostics must contain only MHParameterDiagnostics objects"
            )
        _validate_diagnostic_status(
            diagnostics,
            self.qualification_status,
            self.diagnostics_message,
        )
        object.__setattr__(self, "chains", chains)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(
            self,
            "resolved_metadata",
            _readonly_metadata(self.resolved_metadata),
        )

    def pooled_samples(self, require_qualified: bool = True) -> LpmSampleTable:
        """Return a new table pooling chains only after qualification control.

        Parameters
        ----------
        require_qualified : bool, default=True
            Refuse pooling unless :attr:`qualification_status` is
            ``"qualified"``. Passing ``False`` explicitly permits exploratory
            pooling while retaining the non-qualified status on this result.

        Returns
        -------
        LpmSampleTable
            Independent pooled table. Individual chain tables remain unchanged.
        """
        if not isinstance(require_qualified, bool):
            raise ValueError("require_qualified must be a boolean")
        if require_qualified and self.qualification_status != QUALIFIED:
            raise RuntimeError(
                "MCMC samples cannot be pooled as qualified: ensemble status is "
                f"{self.qualification_status!r}"
            )

        first = self.chains[0].samples
        pooled = LpmSampleTable(
            first.lpm_template,
            c_names=first.get_concentration_names(),
        )
        for chain in self.chains:
            pooled.append(chain.samples)
        return pooled


__all__ = [
    "DIAGNOSTICS_UNAVAILABLE",
    "MHChainResult",
    "MHEnsembleResult",
    "MHParameterDiagnostics",
    "MHPilotResult",
    "NOT_QUALIFIED",
    "QUALIFICATION_STATUSES",
    "QUALIFIED",
    "QualificationStatus",
]
