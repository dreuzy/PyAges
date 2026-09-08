# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for the shared multi-chain MH workflow integration boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyages.calibration.methods.mh import MHConfig, MHConvergenceError
from pyages.config.models import MetropolisHastingsCfg
from pyages.workflows.runtime import mh as runtime_mh


@pytest.mark.parametrize(
    ("stage", "chain_id", "suffix"),
    [
        ("initialization", 0, "initialization"),
        ("pilot", 2, "pilot/chain_002"),
        ("production", 12, "chains/chain_012"),
    ],
)
def test_mh_stage_directory_has_stable_audit_paths(
    tmp_path, stage, chain_id, suffix
) -> None:
    assert runtime_mh._mh_stage_directory(tmp_path, stage, chain_id) == (
        tmp_path / suffix
    )


@pytest.mark.parametrize(
    ("stage", "chain_id", "message"),
    [
        ("initialization", 1, "chain_id 0"),
        ("pilot", 0, "positive"),
        ("production", True, "positive"),
        ("adaptation", 1, "unknown"),
    ],
)
def test_mh_stage_directory_rejects_invalid_engine_requests(
    tmp_path, stage, chain_id, message
) -> None:
    with pytest.raises(ValueError, match=message):
        runtime_mh._mh_stage_directory(tmp_path, stage, chain_id)


def test_build_mh_run_config_translates_all_nested_scientific_controls() -> None:
    config = MetropolisHastingsCfg(
        chains=3,
        seed=987,
        initialization={
            "strategy": "explicit",
            "explicit_starts": [{"mu": 1.0}, {"mu": 2.0}, {"mu": 3.0}],
            "max_attempts": 44,
        },
        pilot={
            "enabled": True,
            "nsteps": 123,
            "burn_in": 0.4,
            "relative_ridge": 2.0e-6,
            "proposal_multiplier": 0.75,
            "save_samples": True,
        },
        diagnostics={
            "max_rhat": 1.02,
            "min_bulk_ess": 222.0,
            "min_tail_ess": 111.0,
            "require_convergence": False,
        },
    )

    translated = runtime_mh.build_mh_run_config(config)

    assert translated.chains == 3
    assert translated.seed == 987
    assert translated.initialization.strategy == "explicit"
    assert translated.initialization.explicit_starts == (
        {"mu": 1.0},
        {"mu": 2.0},
        {"mu": 3.0},
    )
    assert translated.initialization.max_attempts == 44
    assert translated.pilot.nsteps == 123
    assert translated.pilot.burn_in == 0.4
    assert translated.pilot.relative_ridge == 2.0e-6
    assert translated.pilot.proposal_multiplier == 0.75
    assert translated.pilot.save_samples is True
    assert translated.diagnostics.max_rhat == 1.02
    assert translated.diagnostics.min_bulk_ess == 222.0
    assert translated.diagnostics.min_tail_ess == 111.0
    assert translated.diagnostics.require_convergence is False


def test_run_mh_builds_fresh_stage_problems_and_pools_exploratory_run(
    tmp_path, monkeypatch
) -> None:
    ensemble_result = SimpleNamespace(diagnostics=(), diagnostics_message=None)

    def run(factory):
        problems = [
            factory("initialization", 0),
            factory("pilot", 1),
            factory("production", 1),
            factory("production", 2),
        ]
        assert len({id(problem) for problem in problems}) == 4
        return ensemble_result

    engine = SimpleNamespace(run=Mock(side_effect=run))
    engine_class = Mock(return_value=engine)
    pooled = object()
    writer = Mock(return_value=pooled)
    built: list[tuple[object, object]] = []

    def problem_builder(directory):
        problem = object()
        built.append((directory, problem))
        return problem

    monkeypatch.setattr(runtime_mh, "MetropolisHastingsRunner", engine_class)
    monkeypatch.setattr(runtime_mh, "write_mh_run_result", writer)
    config = MetropolisHastingsCfg(
        nsteps=100,
        thinning=1,
        chains=2,
        pilot={"enabled": True, "nsteps": 40},
        diagnostics={"require_convergence": False},
    )
    chain_config = MHConfig(nsteps=100, burn_in=0.2, thinning=1)

    result = runtime_mh._run_mh(
        chain_config,
        runtime_mh.build_mh_run_config(config),
        tmp_path,
        problem_builder,
    )

    assert result is pooled
    assert [directory for directory, _problem in built] == [
        tmp_path / "initialization",
        tmp_path / "pilot" / "chain_001",
        tmp_path / "chains" / "chain_001",
        tmp_path / "chains" / "chain_002",
    ]
    writer.assert_called_once_with(ensemble_result, tmp_path)


def test_run_mh_raises_only_after_failed_run_is_serialized(
    tmp_path, monkeypatch
) -> None:
    ensemble_result = SimpleNamespace(
        diagnostics=(
            SimpleNamespace(
                parameter="mu",
                included_in_qualification=True,
                qualified=False,
            ),
        ),
        diagnostics_message=None,
    )
    engine = SimpleNamespace(run=Mock(return_value=ensemble_result))
    writer = Mock(return_value=None)
    monkeypatch.setattr(
        runtime_mh,
        "MetropolisHastingsRunner",
        Mock(return_value=engine),
    )
    monkeypatch.setattr(runtime_mh, "write_mh_run_result", writer)
    config = MetropolisHastingsCfg(
        nsteps=100,
        thinning=1,
        chains=2,
        diagnostics={"require_convergence": False},
    )

    with pytest.raises(MHConvergenceError, match=r"mu.*preserved") as caught:
        runtime_mh._run_mh(
            MHConfig(nsteps=100, burn_in=0.2, thinning=1),
            runtime_mh.build_mh_run_config(config),
            tmp_path,
            Mock(),
        )

    assert str(tmp_path) not in str(caught.value)

    writer.assert_called_once()
    assert writer.call_args.args[0] is ensemble_result
    assert writer.call_args.args[1] == tmp_path
    assert not writer.call_args.kwargs


def test_build_mh_config_translates_single_date_controls() -> None:
    translated = runtime_mh.build_mh_config(
        MetropolisHastingsCfg(
            nsteps=321,
            burn_in=0.3,
            thinning=7,
            seed=456,
            prior_option=True,
            likelihood=False,
            display_traj=True,
        )
    )

    assert translated.nsteps == 321
    assert translated.burn_in == 0.3
    assert translated.thinning == 7
    assert translated.seed == 456
    assert translated.prior_option is True
    assert translated.likelihood is False
    # Plotting requires a retained trajectory, which the runtime enables
    # internally without exposing a second public workflow switch.
    assert translated.monitor is True
    assert translated.display_traj is True


def test_run_mh_calibration_routes_one_chain_through_the_common_runner(
    tmp_path, monkeypatch
) -> None:
    samples = object()
    record = SimpleNamespace(diagnostics=(), diagnostics_message=None)

    def run(factory):
        factory("initialization", 0)
        factory("production", 1)
        return record

    engine = SimpleNamespace(run=Mock(side_effect=run))
    engine_class = Mock(return_value=engine)
    writer = Mock(return_value=samples)
    problem_builder = Mock()
    monkeypatch.setattr(
        runtime_mh,
        "MetropolisHastingsRunner",
        engine_class,
    )
    monkeypatch.setattr(runtime_mh, "write_mh_run_result", writer)
    config = MetropolisHastingsCfg(
        nsteps=11,
        burn_in=0.0,
        thinning=1,
        seed=456,
    )

    result = runtime_mh.run_mh_calibration(
        config,
        tmp_path,
        problem_builder,
    )

    assert result is samples
    run_config = engine_class.call_args.args[1]
    chain_config = engine_class.call_args.args[0]
    assert chain_config.nsteps == 11
    assert chain_config.seed == 456
    assert run_config.chains == 1
    assert run_config.seed == 456
    assert run_config.initialization.strategy == "bounds_stratified"
    assert run_config.pilot.enabled is False
    engine.run.assert_called_once()
    assert [call.args[0] for call in problem_builder.call_args_list] == [
        tmp_path / "initialization",
        tmp_path / "chains" / "chain_001",
    ]
    writer.assert_called_once_with(record, tmp_path)
