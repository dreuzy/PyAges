# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Adversarial boundary tests for immutable multi-chain run records."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyages.calibration.methods.mh._result_validation import (
    _metrics_are_qualified,
    _validate_diagnostic_status,
    _validate_record_configuration,
    _validate_run_chains,
    _validate_seed_plan,
    _validate_target_signature,
)
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.results import MHParameterDiagnostics
from pyages.calibration.methods.mh.run_config import (
    MHPilotConfig,
    MHRunConfig,
    MHSeedPlan,
)


def _diagnostic(*, qualified: bool, included: bool = True) -> MHParameterDiagnostics:
    return MHParameterDiagnostics(
        parameter="mu",
        rhat=1.001 if qualified else 1.2,
        bulk_ess=500.0 if qualified else 5.0,
        tail_ess=450.0 if qualified else 4.0,
        mcse_mean=0.01,
        posterior_sd=2.0,
        qualified=qualified,
        included_in_qualification=included,
    )


def _seed_plan() -> MHSeedPlan:
    return MHSeedPlan(
        seed=1,
        initialization_seeds=(2, 3),
        pilot_seeds=(4, 5),
        production_seeds=(6, 7),
    )


def test_metric_qualification_rejects_the_wrong_threshold_type() -> None:
    with pytest.raises(TypeError, match="MHDiagnosticsConfig"):
        _metrics_are_qualified(
            rhat=1.0,
            bulk_ess=100.0,
            tail_ess=100.0,
            mcse_mean=0.1,
            thresholds=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("version", [0, -1, True, 1.5])
def test_target_signature_rejects_non_positive_integer_versions(
    version: object,
) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        _validate_target_signature(version, "a" * 64)  # type: ignore[arg-type]


@pytest.mark.parametrize("digest", ["a" * 63, "A" * 64, "g" * 64, 42])
def test_target_signature_rejects_noncanonical_digests(digest: object) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        _validate_target_signature(1, digest)  # type: ignore[arg-type]


def test_run_chain_collection_rejects_empty_and_foreign_values() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _validate_run_chains(())
    with pytest.raises(TypeError, match="only MHChainResult"):
        _validate_run_chains((object(),))  # type: ignore[arg-type]


def test_seed_plan_validation_defends_against_corrupted_deserialization() -> None:
    chains = (SimpleNamespace(seed=6), SimpleNamespace(seed=7))
    with pytest.raises(TypeError, match="MHSeedPlan"):
        _validate_seed_plan(object(), chains)  # type: ignore[arg-type]

    invalid_master = _seed_plan()
    object.__setattr__(invalid_master, "seed", True)
    with pytest.raises(ValueError, match="seed"):
        _validate_seed_plan(invalid_master, chains)  # type: ignore[arg-type]

    invalid_phase = _seed_plan()
    object.__setattr__(invalid_phase, "pilot_seeds", (4, True))
    with pytest.raises(ValueError, match="phase seeds must be integers"):
        _validate_seed_plan(invalid_phase, chains)  # type: ignore[arg-type]

    duplicated = _seed_plan()
    object.__setattr__(duplicated, "pilot_seeds", (4, 6))
    with pytest.raises(ValueError, match="phase seeds must be distinct"):
        _validate_seed_plan(duplicated, chains)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="one seed per chain"):
        _validate_seed_plan(_seed_plan(), chains[:1])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="production chain seeds"):
        _validate_seed_plan(
            _seed_plan(),
            (SimpleNamespace(seed=8), SimpleNamespace(seed=9)),
        )  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("diagnostics", "status", "message", "expected"),
    [
        ((), "unknown", None, "qualification_status"),
        ((), "diagnostics_unavailable", "", "non-empty string"),
        (
            (_diagnostic(qualified=True),),
            "diagnostics_unavailable",
            "failed",
            "partial",
        ),
        ((), "diagnostics_unavailable", None, "require diagnostics_message"),
        ((_diagnostic(qualified=True),), "qualified", "failed", "only when"),
        ((), "qualified", None, "need diagnostics"),
        ((_diagnostic(qualified=False),), "qualified", None, "qualified diagnostics"),
        ((_diagnostic(qualified=True),), "not_qualified", None, "failed gating"),
        (
            (_diagnostic(qualified=True, included=False),),
            "qualified",
            None,
            "qualified diagnostics",
        ),
    ],
)
def test_diagnostic_status_state_machine_rejects_incoherent_records(
    diagnostics: tuple[MHParameterDiagnostics, ...],
    status: str,
    message: str | None,
    expected: str,
) -> None:
    with pytest.raises(ValueError, match=expected):
        _validate_diagnostic_status(
            diagnostics,
            status,  # type: ignore[arg-type]
            message,
            chain_count=2,
        )


def test_not_applicable_diagnostics_are_reserved_for_one_chain() -> None:
    _validate_diagnostic_status((), "not_applicable", None, chain_count=1)

    with pytest.raises(ValueError, match="exactly one chain"):
        _validate_diagnostic_status((), "not_applicable", None, chain_count=2)
    with pytest.raises(ValueError, match="must not contain inter-chain"):
        _validate_diagnostic_status(
            (_diagnostic(qualified=True),),
            "not_applicable",
            None,
            chain_count=1,
        )
    with pytest.raises(ValueError, match="must use qualification_status"):
        _validate_diagnostic_status((), "qualified", None, chain_count=1)
    with pytest.raises(ValueError, match="must use qualification_status"):
        _validate_diagnostic_status(
            (),
            "diagnostics_unavailable",
            "failed",
            chain_count=1,
        )


def test_record_validation_checks_configuration_types_first() -> None:
    run_config = MHRunConfig(chains=2, pilot=MHPilotConfig(enabled=False))
    plan = _seed_plan()
    with pytest.raises(TypeError, match="chain_config"):
        _validate_record_configuration(
            chain_config=object(),  # type: ignore[arg-type]
            run_config=run_config,
            chains=(),
            pilot=None,
            diagnostics=(),
            seed_plan=plan,
        )
    with pytest.raises(TypeError, match="run_config"):
        _validate_record_configuration(
            chain_config=MHConfig(
                nsteps=2, burn_in=0.0, thinning=1, record_trajectory=False
            ),
            run_config=object(),  # type: ignore[arg-type]
            chains=(),
            pilot=None,
            diagnostics=(),
            seed_plan=plan,
        )
