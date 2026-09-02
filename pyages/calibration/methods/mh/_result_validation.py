# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file validates relationships within immutable multi-chain MH results.

"""Validate cross-object invariants of a complete multi-chain MH run.

Result dataclasses remain in :mod:`pyages.calibration.methods.mh.results`.
Keeping their cross-record consistency checks here shortens that public module
without creating another result type or changing its import surface.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from pyages.calibration.methods.mh._diagnostic_contract import (
    build_diagnostic_quantities,
)
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHSeedPlan,
    build_seed_plan,
)
from pyages.calibration.sampling_schedule import strict_retained_sample_count

if TYPE_CHECKING:
    from pyages.calibration.methods.mh.results import (
        MHChainResult,
        MHParameterDiagnostics,
        MHPilotResult,
        QualificationStatus,
    )

_QUALIFIED = "qualified"
_NOT_QUALIFIED = "not_qualified"
_DIAGNOSTICS_UNAVAILABLE = "diagnostics_unavailable"
_QUALIFICATION_STATUSES = frozenset(
    {_QUALIFIED, _NOT_QUALIFIED, _DIAGNOSTICS_UNAVAILABLE}
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
    from pyages.calibration.methods.mh.results import MHChainResult

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
    if any(
        chain._template_sha256 != chains[0]._template_sha256  # noqa: SLF001
        for chain in chains[1:]
    ):
        raise ValueError("production chains must use the same scientific LPM template")


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
    """Enforce the state machine linking diagnostics and qualification status.

    ``diagnostics_unavailable`` represents a calculation failure: it must carry
    an explanatory message and no partial diagnostic records. ``qualified`` and
    ``not_qualified`` represent completed calculations: they require diagnostics,
    forbid an error message, and must contain at least one quantity included in
    the convergence gate.

    A qualified record requires every gating quantity to pass. A non-qualified
    record requires at least one gating failure. Informational derived quantities
    excluded from the gate may fail without changing either terminal status.
    """
    # First separate an unavailable calculation from the two states that carry
    # complete metrics; messages have meaning only in the unavailable state.
    if qualification_status not in _QUALIFICATION_STATUSES:
        raise ValueError(
            f"qualification_status must be one of {sorted(_QUALIFICATION_STATUSES)}"
        )
    if message is not None and (not isinstance(message, str) or not message.strip()):
        raise ValueError("diagnostics_message must be a non-empty string or None")
    if qualification_status == _DIAGNOSTICS_UNAVAILABLE:
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
    # Terminal qualification is derived only from explicitly gating quantities;
    # constant derived quantities can remain recorded as informational metrics.
    gating = tuple(item for item in diagnostics if item.included_in_qualification)
    if qualification_status == _QUALIFIED and (
        not gating or not all(item.qualified for item in gating)
    ):
        raise ValueError("qualified ensembles require qualified diagnostics")
    if qualification_status == _NOT_QUALIFIED and (
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
    """Validate pilot continuity and recover the ensemble's original starts.

    Without a pilot, each production chain begins at the ensemble initialization
    state and its recorded ``initial_params`` can be returned directly. With a
    pilot, production ``initial_params`` must instead match the pilot's final
    states; this function returns the earlier pilot initial states for complete
    run provenance.

    Pilot presence, chain count, retained counts, runtimes, optional saved draws,
    and the configured save policy are checked together. This prevents a record
    assembled from different pilot and production executions from appearing
    internally coherent.
    """
    from pyages.calibration.methods.mh.results import MHPilotResult

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
    # Pilot chains retain without thinning, so their expected sample count is
    # derived independently from the production-chain schedule.
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
    """Bind recorded metrics to quantities and thresholds from this exact run.

    Diagnostic rows must appear once and in the canonical order produced from
    the chain tables: sampled parameters first, followed by the expected derived
    moments. Each row's qualification-gate inclusion is recomputed from the
    quantity contract, so a constant derived value cannot be relabeled as a
    sampled convergence requirement or vice versa.

    The per-row ``qualified`` flag is then recalculated with the ensemble's R-hat,
    ESS, and MCSE thresholds. This rejects valid-looking metrics copied from a
    run with a different schema or convergence policy.
    """
    if not diagnostics:
        return
    names = [diagnostic.parameter for diagnostic in diagnostics]
    if len(set(names)) != len(names):
        raise ValueError("diagnostic parameter names must be unique")
    # Derive names and gating roles from the immutable chain snapshots rather
    # than trusting the serialized diagnostic labels.
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


__all__ = [
    "_metrics_are_qualified",
    "_validate_diagnostic_status",
    "_validate_ensemble_chains",
    "_validate_record_configuration",
    "_validate_seed_plan",
    "_validate_target_signature",
]
