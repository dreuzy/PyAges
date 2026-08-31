# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structured results for pilot, production, and diagnostic MCMC stages."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Literal

import numpy as np
import pandas as pd

from pyages.calibration.methods.mh._diagnostic_contract import (
    build_diagnostic_quantities,
)
from pyages.calibration.methods.mh._immutable import (
    FrozenMapping,
    immutable_float_array,
)
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHSeedPlan,
    build_seed_plan,
)
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.sampling_schedule import strict_retained_sample_count
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
    return FrozenMapping(copied)


def _copied_finite_state(state: Mapping[str, float]) -> Mapping[str, float]:
    """Return one validated detached read-only parameter-state mapping."""
    if not isinstance(state, Mapping):
        raise TypeError("parameter states must be mappings")
    if not state:
        raise ValueError("parameter states must not be empty")
    copied = {name: float(value) for name, value in state.items()}
    if not all(isinstance(name, str) and name for name in copied):
        raise ValueError("parameter names must be non-empty strings")
    if not all(math.isfinite(value) for value in copied.values()):
        raise ValueError("parameter states must contain only finite values")
    return FrozenMapping(copied)


def _validated_pilot_states(
    states: tuple[Mapping[str, float], ...],
) -> tuple[tuple[Mapping[str, float], ...], tuple[str, ...]]:
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
    return immutable_float_array(copied)


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
        copied.append(immutable_float_array(values))
    return tuple(copied)


def _pilot_result_sha256(pilot: "MHPilotResult") -> str:
    """Fingerprint every pilot field used for production provenance."""
    payload = {
        "final_states": pilot.final_states,
        "proposal_multiplier": pilot.proposal_multiplier,
        "acceptance_rates": pilot.acceptance_rates,
        "retained_counts": pilot.retained_counts,
        "initial_states": pilot.initial_states,
        "runtime_seconds": pilot.runtime_seconds,
    }
    digest = sha256(
        json.dumps(
            _snapshot_json_value(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    arrays = (pilot.covariance,) + (() if pilot.samples is None else pilot.samples)
    for values in arrays:
        canonical = np.ascontiguousarray(values, dtype="<f8")
        digest.update(repr(canonical.shape).encode("ascii"))
        digest.update(b"\0")
        digest.update(canonical.tobytes(order="C"))
    return digest.hexdigest()


def _snapshot_json_value(value: Any) -> Any:
    """Return a deterministic JSON-compatible value for integrity snapshots."""
    if isinstance(value, Mapping):
        return {
            str(name): _snapshot_json_value(item)
            for name, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, np.ndarray):
        return _snapshot_json_value(value.tolist())
    if isinstance(value, (tuple, list)):
        return [_snapshot_json_value(item) for item in value]
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _sample_table_sha256(samples: LpmSampleTable) -> str:
    """Fingerprint one chain table and the model schema used to interpret it."""
    samples.validate()
    frame = samples.frame
    template = samples.lpm_template
    parameter_names = tuple(samples.get_param_names())
    model_payload = {
        "class": f"{type(template).__module__}.{type(template).__qualname__}",
        "parameters": [
            {
                "name": name,
                "minimum": float(template.get_p_min(name)),
                "maximum": float(template.get_p_max(name)),
            }
            for name in parameter_names
        ],
        "parameter_units": template.parameter_units,
        "concentrations": samples.get_concentration_names(),
        "moments": template.moments_name(),
        "fixed_scientific_state": template.fixed_scientific_state(),
        "columns": [str(column) for column in frame.columns],
        "dtypes": [str(dtype) for dtype in frame.dtypes],
    }
    digest = sha256(
        json.dumps(
            _snapshot_json_value(model_payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    hashed_rows = pd.util.hash_pandas_object(frame, index=True, categorize=False)
    digest.update(hashed_rows.to_numpy(dtype=np.uint64, copy=False).tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class MHPilotResult:
    """Results retained after learning one common proposal covariance.

    ``initial_states`` records the dispersed pre-pilot starts and
    ``runtime_seconds`` records each pilot's cost. ``samples`` is optional so
    production runs need not retain pilot draws. When present, numerical
    arrays are copied and marked read-only.
    """

    final_states: tuple[Mapping[str, float], ...]
    covariance: np.ndarray
    proposal_multiplier: float
    acceptance_rates: tuple[float, ...]
    retained_counts: tuple[int, ...]
    samples: tuple[np.ndarray, ...] | None = None
    initial_states: tuple[Mapping[str, float], ...] | None = None
    runtime_seconds: tuple[float, ...] | None = None
    _snapshot_sha256: str = field(init=False, repr=False, compare=False)

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
        object.__setattr__(self, "_snapshot_sha256", _pilot_result_sha256(self))

    def validate_snapshot(self) -> None:
        """Reject pilot provenance changed after result construction."""
        if _pilot_result_sha256(self) != self._snapshot_sha256:
            raise RuntimeError("pilot result changed after its provenance snapshot")

    def __deepcopy__(self, _memo: dict[int, object]) -> MHPilotResult:
        """Return self because every reachable pilot value is immutable."""
        return self

    def __reduce__(self) -> tuple[Any, tuple[object, ...]]:
        """Rebuild through validation so unpickled arrays stay immutable."""
        return (
            type(self),
            (
                self.final_states,
                self.covariance,
                self.proposal_multiplier,
                self.acceptance_rates,
                self.retained_counts,
                self.samples,
                self.initial_states,
                self.runtime_seconds,
            ),
        )


@dataclass(frozen=True)
class MHChainResult:
    """Samples and provenance produced by one independent production chain.

    The incoming sample table is detached with a deep copy. A structural and
    row-level digest is retained so later mutation through the intentionally
    mutable :class:`LpmSampleTable` API is detected before diagnostics, pooling,
    or serialization can use stale provenance.
    """

    chain_id: int
    seed: int
    initial_params: Mapping[str, float]
    samples: LpmSampleTable
    acceptance_rate: float
    runtime_seconds: float
    _samples_sha256: str = field(init=False, repr=False, compare=False)

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
        copied_samples = deepcopy(self.samples)
        copied_samples.validate()
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
        object.__setattr__(self, "samples", copied_samples)
        object.__setattr__(self, "acceptance_rate", float(self.acceptance_rate))
        object.__setattr__(self, "runtime_seconds", float(self.runtime_seconds))
        object.__setattr__(
            self, "_samples_sha256", _sample_table_sha256(copied_samples)
        )

    def validate_snapshot(self) -> None:
        """Reject sample or model mutations made after chain construction."""
        if _sample_table_sha256(self.samples) != self._samples_sha256:
            raise RuntimeError(
                f"production chain {self.chain_id} samples changed after their "
                "diagnostic snapshot"
            )


_DIAGNOSTIC_METRIC_NAMES = (
    "rhat",
    "bulk_ess",
    "tail_ess",
    "mcse_mean",
    "posterior_sd",
)


def _normalized_diagnostic_metrics(
    diagnostic: "MHParameterDiagnostics",
) -> dict[str, float]:
    """Convert diagnostic scalars without accepting booleans."""
    normalized: dict[str, float] = {}
    for name in _DIAGNOSTIC_METRIC_NAMES:
        raw_value = getattr(diagnostic, name)
        if isinstance(raw_value, (bool, np.bool_)):
            raise ValueError(f"{name} must be numeric, not boolean")
        try:
            normalized[name] = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
    return normalized


def _validate_diagnostic_metric_domains(
    metrics: Mapping[str, float],
    *,
    qualified: bool,
) -> None:
    """Reject NaN, negative, and internally impossible metrics."""
    if math.isnan(metrics["rhat"]) or metrics["rhat"] <= 0.0:
        raise ValueError("rhat must be positive or positive infinity")
    for name in ("bulk_ess", "tail_ess"):
        value = metrics[name]
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
    if math.isnan(metrics["mcse_mean"]) or metrics["mcse_mean"] < 0.0:
        raise ValueError("mcse_mean must be non-negative or positive infinity")
    if not math.isfinite(metrics["posterior_sd"]) or metrics["posterior_sd"] < 0.0:
        raise ValueError("posterior_sd must be finite and non-negative")
    if qualified and (
        not math.isfinite(metrics["rhat"]) or not math.isfinite(metrics["mcse_mean"])
    ):
        raise ValueError("qualified diagnostics require finite R-hat and MCSE")


@dataclass(frozen=True)
class MHParameterDiagnostics:
    """Convergence metrics for one sampled or derived posterior quantity.

    ``included_in_qualification`` is false only for derived quantities that are
    constant across all retained production draws and whose R-hat and ESS are
    therefore undefined. Native sampled parameters always remain part of the
    convergence gate.
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
        """Normalize metrics and reject impossible diagnostic records."""
        if not isinstance(self.parameter, str) or not self.parameter:
            raise ValueError("parameter must be a non-empty string")
        if not isinstance(self.qualified, bool):
            raise ValueError("qualified must be a boolean")
        if not isinstance(self.included_in_qualification, bool):
            raise ValueError("included_in_qualification must be a boolean")
        normalized = _normalized_diagnostic_metrics(self)
        _validate_diagnostic_metric_domains(normalized, qualified=self.qualified)
        for name, value in normalized.items():
            object.__setattr__(self, name, value)

    @classmethod
    def from_metrics(
        cls,
        *,
        parameter: str,
        rhat: float,
        bulk_ess: float,
        tail_ess: float,
        mcse_mean: float,
        posterior_sd: float,
        thresholds: MHDiagnosticsConfig,
        included_in_qualification: bool = True,
    ) -> "MHParameterDiagnostics":
        """Build one record whose qualification is derived from its metrics."""
        qualified = _metrics_are_qualified(
            rhat=rhat,
            bulk_ess=bulk_ess,
            tail_ess=tail_ess,
            mcse_mean=mcse_mean,
            thresholds=thresholds,
        )
        return cls(
            parameter=parameter,
            rhat=rhat,
            bulk_ess=bulk_ess,
            tail_ess=tail_ess,
            mcse_mean=mcse_mean,
            posterior_sd=posterior_sd,
            qualified=qualified,
            included_in_qualification=included_in_qualification,
        )


def _metrics_are_qualified(
    *,
    rhat: float,
    bulk_ess: float,
    tail_ess: float,
    mcse_mean: float,
    thresholds: MHDiagnosticsConfig,
) -> bool:
    """Return the single canonical multi-chain qualification decision."""
    if not isinstance(thresholds, MHDiagnosticsConfig):
        raise TypeError("thresholds must be an MHDiagnosticsConfig")
    return bool(
        math.isfinite(rhat)
        and rhat < thresholds.max_rhat
        and bulk_ess >= thresholds.min_bulk_ess
        and tail_ess >= thresholds.min_tail_ess
        and math.isfinite(mcse_mean)
    )


def _validate_ensemble_chains(chains: tuple[MHChainResult, ...]) -> None:
    """Validate production-chain types and canonical identifiers."""
    if not chains:
        raise ValueError("chains must contain at least one production chain")
    if any(not isinstance(chain, MHChainResult) for chain in chains):
        raise TypeError("chains must contain only MHChainResult objects")
    for chain in chains:
        chain.validate_snapshot()
    chain_ids = tuple(chain.chain_id for chain in chains)
    expected_ids = tuple(range(1, len(chains) + 1))
    if chain_ids != expected_ids:
        raise ValueError(
            "production chain identifiers must be ordered exactly from 1 to N"
        )
    reference_parameters = chains[0].samples.get_param_names()
    reference_concentrations = chains[0].samples.get_concentration_names()
    if any(
        chain.samples.get_param_names() != reference_parameters
        or chain.samples.get_concentration_names() != reference_concentrations
        for chain in chains[1:]
    ):
        raise ValueError("production chains must use the same sample-table schema")


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


def _validate_record_config_types_and_counts(
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    chains: tuple[MHChainResult, ...],
    seed_plan: MHSeedPlan,
) -> None:
    """Bind chain counts, retained draws, and random streams to configuration."""
    if not isinstance(chain_config, MHConfig):
        raise TypeError("chain_config must be an MHConfig")
    if not isinstance(ensemble_config, MHEnsembleConfig):
        raise TypeError("ensemble_config must be an MHEnsembleConfig")
    if len(chains) != ensemble_config.chains:
        raise ValueError("production chain count does not match ensemble_config")
    expected_draws = chain_config.retained_sample_count()
    if any(len(chain.samples.frame) != expected_draws for chain in chains):
        raise ValueError("production retained counts do not match chain_config")
    if seed_plan != build_seed_plan(ensemble_config):
        raise ValueError("seed_plan does not match ensemble_config")


def _initialization_states_from_pilot_contract(
    ensemble_config: MHEnsembleConfig,
    chains: tuple[MHChainResult, ...],
    pilot: MHPilotResult | None,
) -> tuple[Mapping[str, float], ...]:
    """Validate pilot provenance and return the pre-pilot chain starts."""
    if ensemble_config.pilot.enabled != (pilot is not None):
        raise ValueError("pilot presence does not match ensemble_config")
    if pilot is None:
        return tuple(chain.initial_params for chain in chains)
    if not isinstance(pilot, MHPilotResult):
        raise TypeError("pilot must be an MHPilotResult or None")
    if len(pilot.final_states) != ensemble_config.chains:
        raise ValueError("pilot chain count does not match ensemble_config")
    if pilot.initial_states is None:
        raise ValueError("complete run records require pilot initial_states")
    if pilot.runtime_seconds is None:
        raise ValueError("complete run records require pilot runtimes")
    expected_draws = strict_retained_sample_count(
        ensemble_config.pilot.nstep,
        ensemble_config.pilot.burn_in,
        1,
    )
    if any(count != expected_draws for count in pilot.retained_counts):
        raise ValueError("pilot retained counts do not match ensemble_config")
    if ensemble_config.pilot.save_samples != (pilot.samples is not None):
        raise ValueError("saved pilot samples do not match ensemble_config")
    if any(
        dict(chain.initial_params) != dict(final_state)
        for chain, final_state in zip(chains, pilot.final_states, strict=True)
    ):
        raise ValueError("production starts must match pilot final states")
    return pilot.initial_states


def _validate_explicit_initialization(
    ensemble_config: MHEnsembleConfig,
    initialization_states: tuple[Mapping[str, float], ...],
) -> None:
    """Bind recorded starts to explicit user configuration when selected."""
    explicit_starts = ensemble_config.initialization.explicit_starts
    if explicit_starts is None:
        return
    if len(explicit_starts) != ensemble_config.chains:
        raise ValueError("explicit_starts must contain one state per chain")
    if any(
        dict(actual) != dict(expected)
        for actual, expected in zip(
            initialization_states,
            explicit_starts,
            strict=True,
        )
    ):
        raise ValueError("recorded initial states do not match explicit_starts")


def _validate_diagnostics_against_config(
    ensemble_config: MHEnsembleConfig,
    chains: tuple[MHChainResult, ...],
    diagnostics: tuple[MHParameterDiagnostics, ...],
) -> None:
    """Bind recorded diagnostics to the canonical scientific quantity contract."""
    if not diagnostics:
        return
    names = [diagnostic.parameter for diagnostic in diagnostics]
    if len(set(names)) != len(names):
        raise ValueError("diagnostic parameter names must be unique")
    quantities = build_diagnostic_quantities(tuple(chain.samples for chain in chains))
    expected_names = tuple(quantity.name for quantity in quantities)
    if tuple(names) != expected_names:
        raise ValueError(
            "diagnostics must follow exactly the sampled parameters and expected "
            f"moments {list(expected_names)}"
        )
    thresholds = ensemble_config.diagnostics
    for diagnostic, quantity in zip(diagnostics, quantities, strict=True):
        values = quantity.values
        if not np.all(np.isfinite(values)):
            raise ValueError(
                f"recorded diagnostic {diagnostic.parameter!r} requires finite "
                "production values"
            )
        expected_inclusion = quantity.included_in_qualification
        if diagnostic.included_in_qualification != expected_inclusion:
            role = "included" if expected_inclusion else "excluded"
            raise ValueError(
                f"diagnostic {diagnostic.parameter!r} must be {role} in qualification"
            )
        expected = _metrics_are_qualified(
            rhat=diagnostic.rhat,
            bulk_ess=diagnostic.bulk_ess,
            tail_ess=diagnostic.tail_ess,
            mcse_mean=diagnostic.mcse_mean,
            thresholds=thresholds,
        )
        if diagnostic.qualified != expected:
            raise ValueError(
                f"diagnostic qualification for {diagnostic.parameter!r} does not "
                "match ensemble_config thresholds"
            )


def _validate_record_configuration(
    *,
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    chains: tuple[MHChainResult, ...],
    pilot: MHPilotResult | None,
    diagnostics: tuple[MHParameterDiagnostics, ...],
    seed_plan: MHSeedPlan,
) -> None:
    """Bind every recorded result invariant to the configuration that produced it."""
    _validate_record_config_types_and_counts(
        chain_config,
        ensemble_config,
        chains,
        seed_plan,
    )
    initialization_states = _initialization_states_from_pilot_contract(
        ensemble_config,
        chains,
        pilot,
    )
    _validate_explicit_initialization(ensemble_config, initialization_states)
    _validate_diagnostics_against_config(ensemble_config, chains, diagnostics)


@dataclass(frozen=True)
class MHRunRecord:
    """Immutable configuration and results for one complete MH ensemble run.

    ``resolved_metadata`` contains detached proposal/prior values captured by
    the samplers immediately after preparation and before their transition
    loops.  Keeping this snapshot on the result prevents later input-file
    changes from altering the provenance eventually serialized for the run.
    """

    chain_config: MHConfig
    ensemble_config: MHEnsembleConfig
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
        """Validate the complete run contract and detach caller-owned sequences."""
        chains = tuple(self.chains)
        diagnostics = tuple(self.diagnostics)
        if self.pilot is not None and not isinstance(self.pilot, MHPilotResult):
            raise TypeError("pilot must be an MHPilotResult or None")
        if self.pilot is not None:
            self.pilot.validate_snapshot()
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
        _validate_record_configuration(
            chain_config=self.chain_config,
            ensemble_config=self.ensemble_config,
            chains=chains,
            pilot=self.pilot,
            diagnostics=diagnostics,
            seed_plan=self.seed_plan,
        )

    def validate_integrity(self) -> None:
        """Revalidate mutable table snapshots before consuming this record."""
        _validate_ensemble_chains(self.chains)
        if self.pilot is not None:
            self.pilot.validate_snapshot()
        _validate_seed_plan(self.seed_plan, self.chains)
        _validate_record_configuration(
            chain_config=self.chain_config,
            ensemble_config=self.ensemble_config,
            chains=self.chains,
            pilot=self.pilot,
            diagnostics=self.diagnostics,
            seed_plan=self.seed_plan,
        )
        _validate_diagnostic_status(
            self.diagnostics,
            self.qualification_status,
            self.diagnostics_message,
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

        Raises
        ------
        ValueError
            If ``require_qualified`` is not a boolean.
        MHConvergenceError
            If qualification is required and this run is not ``"qualified"``.

        """
        if not isinstance(require_qualified, bool):
            raise ValueError("require_qualified must be a boolean")
        self.validate_integrity()
        if require_qualified and self.qualification_status != QUALIFIED:
            raise MHConvergenceError(
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
    "MHParameterDiagnostics",
    "MHPilotResult",
    "MHRunRecord",
    "NOT_QUALIFIED",
    "QUALIFICATION_STATUSES",
    "QUALIFIED",
    "QualificationStatus",
]
