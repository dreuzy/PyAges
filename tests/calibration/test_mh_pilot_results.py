# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for MCMC pilot helpers and structured ensemble results."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pyages.calibration.methods.mh.ensemble_config import MHSeedPlan
from pyages.calibration.methods.mh.pilot import (
    automatic_proposal_multiplier,
    pooled_within_chain_covariance,
)
from pyages.calibration.methods.mh.results import (
    MHChainResult,
    MHEnsembleResult,
    MHParameterDiagnostics,
    MHPilotResult,
)
from pyages.lpm import build_lpm
from pyages.lpm.samples.table import LpmSampleTable


def _sample_table(value: float) -> LpmSampleTable:
    model = build_lpm("exp")
    parameter = model.get_param_names()[0]
    table = LpmSampleTable(model, c_names=["cfc11"])
    table.append_sample(
        {parameter: value}, obj_function=value**2, concentrations=[value / 10.0]
    )
    return table


def _diagnostic(*, qualified: bool = True) -> MHParameterDiagnostics:
    return MHParameterDiagnostics(
        parameter="mu",
        rhat=1.001,
        bulk_ess=800.0,
        tail_ess=600.0,
        mcse_mean=0.1,
        posterior_sd=2.0,
        qualified=qualified,
    )


def _seed_plan(*production_seeds: int) -> MHSeedPlan:
    """Build compact, distinct phase seeds for result-contract tests."""
    return MHSeedPlan(
        master_seed=17,
        initialization_seeds=tuple(seed + 100 for seed in production_seeds),
        pilot_seeds=tuple(seed + 200 for seed in production_seeds),
        production_seeds=production_seeds,
    )


def _ensemble_result(
    chains: tuple[MHChainResult, ...],
    diagnostics: tuple[MHParameterDiagnostics, ...],
    status: str,
) -> MHEnsembleResult:
    """Construct an ensemble with valid compact scientific provenance."""
    return MHEnsembleResult(
        chains=chains,
        pilot=None,
        diagnostics=diagnostics,
        qualification_status=status,
        seed_plan=_seed_plan(*(chain.seed for chain in chains)),
        target_signature_version=1,
        target_sha256="a" * 64,
    )


def test_pooled_covariance_uses_only_weighted_within_chain_variation() -> None:
    base = np.array([[0.0, 0.0], [2.0, 0.0], [0.0, 4.0]])
    chains = (base, base + np.array([100.0, -50.0]))

    actual = pooled_within_chain_covariance(chains, relative_ridge=0.0)
    expected = np.cov(base, rowvar=False, ddof=1)

    assert np.allclose(actual, expected)
    assert np.all(np.linalg.eigvalsh(actual) > 0.0)


def test_pooled_covariance_regularizes_a_singular_pilot_geometry() -> None:
    draws = np.column_stack((np.arange(5.0), 2.0 * np.arange(5.0)))

    covariance = pooled_within_chain_covariance((draws, draws + 50.0))

    assert np.allclose(covariance, covariance.T)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)


@pytest.mark.parametrize(
    "chains, message",
    [
        ((), "at least one"),
        ((np.ones((1, 2)),), "at least two"),
        ((np.ones(3),), "at least two"),
        ((np.ones((2, 0)),), "at least two"),
        ((np.array([[1.0], [np.nan]]),), "finite"),
        ((np.ones((2, 1)), np.ones((2, 2))), "same parameter"),
    ],
)
def test_pooled_covariance_rejects_invalid_pilot_matrices(chains, message) -> None:
    with pytest.raises(ValueError, match=message):
        pooled_within_chain_covariance(chains)


def test_automatic_proposal_multiplier_validates_dimension() -> None:
    assert automatic_proposal_multiplier(4) == pytest.approx(1.19)
    assert automatic_proposal_multiplier(np.int64(1)) == pytest.approx(2.38)
    for invalid in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match="positive integer"):
            automatic_proposal_multiplier(invalid)


def test_pilot_result_defensively_copies_covariance_and_optional_samples() -> None:
    covariance = np.array([[4.0]])
    saved = np.array([[1.0], [2.0], [3.0]])
    result = MHPilotResult(
        final_states=({"mu": 3.0},),
        covariance=covariance,
        proposal_multiplier=2.38,
        acceptance_rates=(0.3,),
        retained_counts=(3,),
        samples=(saved,),
    )

    covariance[0, 0] = 99.0
    saved[0, 0] = 99.0

    assert result.covariance[0, 0] == 4.0
    assert result.samples is not None
    assert result.samples[0][0, 0] == 1.0
    assert not result.covariance.flags.writeable
    assert not result.samples[0].flags.writeable


def test_pilot_result_rejects_misaligned_metadata() -> None:
    with pytest.raises(ValueError, match="one finite probability"):
        MHPilotResult(
            final_states=({"mu": 3.0}, {"mu": 4.0}),
            covariance=np.array([[1.0]]),
            proposal_multiplier=2.38,
            acceptance_rates=(0.3,),
            retained_counts=(3, 3),
        )


def test_pooled_samples_are_independent_and_guarded_by_qualification() -> None:
    first = _sample_table(10.0)
    second = _sample_table(20.0)
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, first, 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, second, 0.30, 1.2),
    )
    result = _ensemble_result(chains, (_diagnostic(),), "qualified")

    pooled = result.pooled_samples()
    parameter = pooled.get_param_names()[0]

    assert pooled.frame[parameter].tolist() == [10.0, 20.0]
    pooled.frame.loc[0, parameter] = 999.0
    assert first.frame.loc[0, parameter] == 10.0
    assert second.frame.loc[0, parameter] == 20.0

    exploratory = _ensemble_result(
        chains, (_diagnostic(qualified=False),), "not_qualified"
    )
    with pytest.raises(RuntimeError, match="cannot be pooled as qualified"):
        exploratory.pooled_samples()
    assert len(exploratory.pooled_samples(require_qualified=False).frame) == 2


def test_ensemble_status_and_chain_identifiers_are_validated() -> None:
    chain = MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0)
    with pytest.raises(ValueError, match="qualification_status"):
        _ensemble_result((chain,), (), "unknown")
    noncanonical = MHChainResult(3, 102, {"mu": 20.0}, _sample_table(20.0), 0.25, 1.0)
    with pytest.raises(ValueError, match="ordered exactly from 1 to N"):
        _ensemble_result(
            (chain, noncanonical),
            (_diagnostic(qualified=False),),
            "not_qualified",
        )


def test_ensemble_result_validates_seed_and_target_provenance() -> None:
    chain = MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0)
    with pytest.raises(ValueError, match="production chain seeds"):
        MHEnsembleResult(
            chains=(chain,),
            pilot=None,
            diagnostics=(_diagnostic(),),
            qualification_status="qualified",
            seed_plan=_seed_plan(999),
            target_signature_version=1,
            target_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        MHEnsembleResult(
            chains=(chain,),
            pilot=None,
            diagnostics=(_diagnostic(),),
            qualification_status="qualified",
            seed_plan=_seed_plan(101),
            target_signature_version=1,
            target_sha256="not-a-digest",
        )


def test_chain_result_validates_rates_and_runtime() -> None:
    table = _sample_table(10.0)
    with pytest.raises(ValueError, match="finite probability"):
        MHChainResult(1, 101, {"mu": 10.0}, table, math.nan, 1.0)
    with pytest.raises(ValueError, match="non-negative"):
        MHChainResult(1, 101, {"mu": 10.0}, table, 0.25, -1.0)
    with pytest.raises(ValueError, match="positive integer"):
        MHChainResult(0, 101, {"mu": 10.0}, table, 0.25, 1.0)
