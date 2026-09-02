# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for MCMC pilot helpers and structured ensemble results."""

from __future__ import annotations

import copy
import math
import pickle
from dataclasses import asdict, replace

import numpy as np
import pytest

from pyages.calibration.methods.mh._diagnostic_contract import (
    build_diagnostic_quantities,
)
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
    MHSeedPlan,
    build_seed_plan,
)
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.methods.mh.pilot import (
    automatic_proposal_multiplier,
    pooled_within_chain_covariance,
)
from pyages.calibration.methods.mh.results import (
    MHChainResult,
    MHParameterDiagnostics,
    MHPilotResult,
    MHRunRecord,
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
    table.add_moments()
    return table


def _diagnostic(*, qualified: bool = True) -> MHParameterDiagnostics:
    return MHParameterDiagnostics(
        parameter="mu",
        rhat=1.001 if qualified else 1.2,
        bulk_ess=800.0 if qualified else 5.0,
        tail_ess=600.0 if qualified else 4.0,
        mcse_mean=0.1,
        posterior_sd=2.0,
        qualified=qualified,
    )


def test_diagnostic_quantity_contract_fixes_order_and_exact_inclusion_rule() -> None:
    first = _sample_table(10.0)
    second = _sample_table(10.0)
    for table in (first, second):
        table.frame.loc[:, "std"] = 3.0
    first.frame.loc[:, "mean"] = 11.0
    second.frame.loc[:, "mean"] = 22.0

    quantities = build_diagnostic_quantities((first, second))

    expected_names = ("mu", *first.lpm_template.moments_name())
    assert tuple(quantity.name for quantity in quantities) == expected_names
    inclusion = {
        quantity.name: quantity.included_in_qualification for quantity in quantities
    }
    assert inclusion == {name: name in {"mu", "mean"} for name in expected_names}
    assert quantities[0].values.shape == (2, 1)


def test_diagnostic_quantity_contract_rejects_non_table_inputs_clearly() -> None:
    with pytest.raises(TypeError, match="sequence of LpmSampleTable"):
        build_diagnostic_quantities(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="only LpmSampleTable"):
        build_diagnostic_quantities((object(),))  # type: ignore[arg-type]


def test_diagnostic_quantity_contract_rejects_non_numeric_columns_clearly() -> None:
    first = _sample_table(10.0)
    second = _sample_table(20.0)
    second.frame["mean"] = ["not-numeric"]

    with pytest.raises(ValueError, match="'mean' in chain 2 must be numeric"):
        build_diagnostic_quantities((first, second))


def test_diagnostic_quantity_contract_rejects_zero_retained_draws_clearly() -> None:
    first = _sample_table(10.0)
    second = _sample_table(20.0)
    for table in (first, second):
        table.frame.drop(index=table.frame.index, inplace=True)

    with pytest.raises(ValueError, match="at least one draw per chain"):
        build_diagnostic_quantities((first, second))


def _record_configs(chain_count: int = 2) -> tuple[MHConfig, MHEnsembleConfig]:
    """Build compact configurations retaining one row per production chain."""
    return (
        MHConfig(nstep=2, burn_in=0.0, nskip=1, monitor=False),
        MHEnsembleConfig(
            chains=chain_count,
            master_seed=17,
            initialization=MHInitializationConfig(strategy="model_default"),
            pilot=MHPilotConfig(enabled=False),
            diagnostics=MHDiagnosticsConfig(
                max_rhat=1.05,
                min_bulk_ess=10.0,
                min_tail_ess=10.0,
            ),
        ),
    )


def _ensemble_result(
    chains: tuple[MHChainResult, ...],
    diagnostics: tuple[MHParameterDiagnostics, ...],
    status: str,
) -> MHRunRecord:
    """Construct an ensemble with valid compact scientific provenance."""
    chain_config, ensemble_config = _record_configs(len(chains))
    if len(diagnostics) == 1 and diagnostics[0].parameter == "mu":
        names = tuple(
            dict.fromkeys(
                tuple(chains[0].samples.get_param_names())
                + tuple(chains[0].samples.lpm_template.moments_name())
            )
        )
        diagnostics = tuple(replace(diagnostics[0], parameter=name) for name in names)
    seed_plan = build_seed_plan(ensemble_config)
    bound_chains = tuple(
        MHChainResult(
            chain_id=chain.chain_id,
            seed=seed_plan.production_seeds[index],
            initial_params=chain.initial_params,
            samples=chain.samples,
            acceptance_rate=chain.acceptance_rate,
            runtime_seconds=chain.runtime_seconds,
        )
        for index, chain in enumerate(chains)
    )
    return MHRunRecord(
        chain_config=chain_config,
        ensemble_config=ensemble_config,
        chains=bound_chains,
        pilot=None,
        diagnostics=diagnostics,
        qualification_status=status,
        seed_plan=seed_plan,
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
    initial_state = {"mu": 1.0}
    final_state = {"mu": 3.0}
    result = MHPilotResult(
        final_states=(final_state,),
        covariance=covariance,
        proposal_multiplier=2.38,
        acceptance_rates=(0.3,),
        retained_counts=(3,),
        samples=(saved,),
        initial_states=(initial_state,),
    )

    covariance[0, 0] = 99.0
    saved[0, 0] = 99.0
    initial_state["mu"] = 99.0
    final_state["mu"] = 99.0

    assert result.covariance[0, 0] == 4.0
    assert result.samples is not None
    assert result.samples[0][0, 0] == 1.0
    assert result.initial_states is not None
    assert result.initial_states[0]["mu"] == 1.0
    assert result.final_states[0]["mu"] == 3.0
    assert not result.covariance.flags.writeable
    assert not result.samples[0].flags.writeable
    with pytest.raises(ValueError, match="cannot set WRITEABLE flag"):
        result.covariance.setflags(write=True)
    with pytest.raises(ValueError, match="cannot set WRITEABLE flag"):
        result.samples[0].setflags(write=True)
    assert copy.deepcopy(result) is result
    restored = pickle.loads(pickle.dumps(result))
    restored.validate_snapshot()
    with pytest.raises(ValueError, match="cannot set WRITEABLE flag"):
        restored.covariance.setflags(write=True)
    with pytest.raises(TypeError):
        result.final_states[0]["mu"] = 5.0


def test_pilot_result_snapshot_detects_adversarial_attribute_replacement() -> None:
    result = MHPilotResult(
        final_states=({"mu": 3.0},),
        covariance=np.array([[1.0]]),
        proposal_multiplier=1.0,
        acceptance_rates=(0.3,),
        retained_counts=(2,),
    )
    object.__setattr__(result, "covariance", np.array([[9.0]]))

    with pytest.raises(RuntimeError, match="pilot result changed"):
        result.validate_snapshot()


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
    pooled.lpm_template.set_param_from_array([42.0])
    assert result.chains[0].samples.lpm_template.p[parameter] != 42.0

    exploratory = _ensemble_result(
        chains, (_diagnostic(qualified=False),), "not_qualified"
    )
    with pytest.raises(MHConvergenceError, match="cannot be pooled as qualified"):
        exploratory.pooled_samples()
    assert len(exploratory.pooled_samples(require_qualified=False).frame) == 2


def test_ensemble_status_and_chain_identifiers_are_validated() -> None:
    chain = MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0)
    second = MHChainResult(
        2,
        102,
        {"mu": 20.0},
        _sample_table(20.0),
        0.25,
        1.0,
    )
    with pytest.raises(ValueError, match="qualification_status"):
        _ensemble_result((chain, second), (), "unknown")
    noncanonical = MHChainResult(3, 102, {"mu": 20.0}, _sample_table(20.0), 0.25, 1.0)
    with pytest.raises(ValueError, match="ordered exactly from 1 to N"):
        _ensemble_result(
            (chain, noncanonical),
            (_diagnostic(qualified=False),),
            "not_qualified",
        )


def test_chain_result_requires_initial_state_parameter_identity() -> None:
    with pytest.raises(ValueError, match="exact ordered sample parameters"):
        MHChainResult(
            1,
            101,
            {"wrong": 10.0},
            _sample_table(10.0),
            0.25,
            1.0,
        )


def test_ensemble_rejects_same_named_parameters_from_different_templates() -> None:
    first = _sample_table(10.0)
    second = _sample_table(20.0)
    second.lpm_template._param_manager._calibration_max["mu"] = (  # noqa: SLF001
        200.0
    )
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, first, 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, second, 0.25, 1.0),
    )

    with pytest.raises(ValueError, match="same scientific LPM template"):
        _ensemble_result(
            chains,
            (_diagnostic(qualified=False),),
            "not_qualified",
        )


def test_run_record_validates_seed_and_target_provenance() -> None:
    chain_config, ensemble_config = _record_configs()
    seed_plan = build_seed_plan(ensemble_config)
    chains = tuple(
        MHChainResult(
            index,
            seed,
            {"mu": value},
            _sample_table(value),
            0.25,
            1.0,
        )
        for index, (seed, value) in enumerate(
            zip(seed_plan.production_seeds, (10.0, 20.0), strict=True),
            start=1,
        )
    )
    wrong_seed_plan = MHSeedPlan(
        master_seed=seed_plan.master_seed,
        initialization_seeds=seed_plan.initialization_seeds,
        pilot_seeds=seed_plan.pilot_seeds,
        production_seeds=(999, seed_plan.production_seeds[1]),
    )
    with pytest.raises(ValueError, match="production chain seeds"):
        MHRunRecord(
            chain_config=chain_config,
            ensemble_config=ensemble_config,
            chains=chains,
            pilot=None,
            diagnostics=(_diagnostic(),),
            qualification_status="qualified",
            seed_plan=wrong_seed_plan,
            target_signature_version=1,
            target_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        MHRunRecord(
            chain_config=chain_config,
            ensemble_config=ensemble_config,
            chains=chains,
            pilot=None,
            diagnostics=(_diagnostic(),),
            qualification_status="qualified",
            seed_plan=seed_plan,
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


def test_chain_result_copies_and_freezes_initial_state() -> None:
    initial = {"mu": 10.0}
    result = MHChainResult(
        1,
        101,
        initial,
        _sample_table(10.0),
        0.25,
        1.0,
    )

    initial["mu"] = 99.0

    assert result.initial_params["mu"] == 10.0
    with pytest.raises(TypeError):
        result.initial_params["mu"] = 20.0


def test_run_record_detects_chain_table_mutation_before_pooling() -> None:
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, _sample_table(20.0), 0.30, 1.2),
    )
    result = _ensemble_result(chains, (_diagnostic(),), "qualified")
    result.chains[0].samples.frame.loc[0, "mu"] = 999.0

    with pytest.raises(RuntimeError, match="changed after their diagnostic snapshot"):
        result.pooled_samples()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("rhat", math.nan, "rhat"),
        ("bulk_ess", -1.0, "bulk_ess"),
        ("tail_ess", math.inf, "tail_ess"),
        ("mcse_mean", -0.1, "mcse_mean"),
        ("posterior_sd", math.nan, "posterior_sd"),
    ],
)
def test_parameter_diagnostics_reject_impossible_metrics(
    field: str,
    value: float,
    message: str,
) -> None:
    values = {
        "parameter": "mu",
        "rhat": 1.001,
        "bulk_ess": 800.0,
        "tail_ess": 600.0,
        "mcse_mean": 0.1,
        "posterior_sd": 2.0,
        "qualified": False,
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        MHParameterDiagnostics(**values)


def test_run_record_rejects_qualification_inconsistent_with_thresholds() -> None:
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, _sample_table(20.0), 0.30, 1.2),
    )
    inconsistent = MHParameterDiagnostics(
        parameter="mu",
        rhat=1.001,
        bulk_ess=800.0,
        tail_ess=600.0,
        mcse_mean=0.1,
        posterior_sd=2.0,
        qualified=False,
    )

    with pytest.raises(ValueError, match="does not match ensemble_config thresholds"):
        _ensemble_result(chains, (inconsistent,), "not_qualified")


def test_run_record_requires_the_exact_diagnostic_schema() -> None:
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, _sample_table(20.0), 0.30, 1.2),
    )
    complete = _ensemble_result(chains, (_diagnostic(),), "qualified")
    fake = replace(_diagnostic(), parameter="totally_fake")

    with pytest.raises(ValueError, match="exactly the sampled parameters"):
        replace(complete, diagnostics=(fake,))


def test_run_record_requires_exact_diagnostic_qualification_inclusion() -> None:
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, _sample_table(10.0), 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, _sample_table(20.0), 0.30, 1.2),
    )
    complete = _ensemble_result(chains, (_diagnostic(),), "qualified")
    excluded_native = tuple(
        replace(item, included_in_qualification=False)
        if item.parameter == "mu"
        else item
        for item in complete.diagnostics
    )
    with pytest.raises(ValueError, match="'mu' must be included"):
        replace(complete, diagnostics=excluded_native)

    first_constant = _sample_table(10.0)
    second_constant = _sample_table(20.0)
    first_constant.frame.loc[:, "std"] = 0.0
    second_constant.frame.loc[:, "std"] = 0.0
    constant_chains = (
        MHChainResult(1, 101, {"mu": 10.0}, first_constant, 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, second_constant, 0.30, 1.2),
    )
    with pytest.raises(ValueError, match="'std' must be excluded"):
        _ensemble_result(constant_chains, (_diagnostic(),), "qualified")


def test_run_record_reports_a_diagnostic_missing_from_one_chain() -> None:
    first = _sample_table(10.0)
    second = _sample_table(20.0)
    second.frame.drop(columns="mean", inplace=True)
    chains = (
        MHChainResult(1, 101, {"mu": 10.0}, first, 0.25, 1.0),
        MHChainResult(2, 102, {"mu": 20.0}, second, 0.30, 1.2),
    )

    with pytest.raises(ValueError, match="missing diagnostic 'mean'"):
        _ensemble_result(chains, (_diagnostic(),), "qualified")


def test_mh_config_frozen_payload_is_copy_and_pickle_safe() -> None:
    config = MHConfig(initial_params={"mu": 10.0})

    assert copy.deepcopy(config) == config
    assert asdict(config)["initial_params"] == {"mu": 10.0}
    assert pickle.loads(pickle.dumps(config)) == config
