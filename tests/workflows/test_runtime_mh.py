# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for the shared multi-chain MH workflow integration boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyages.calibration.methods.mh import MHConfig, MHConvergenceError
from pyages.config.models import LauncherMetropolisCfg, MHMultichainCfg
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


def test_build_mh_ensemble_config_translates_all_nested_scientific_controls() -> None:
    config = MHMultichainCfg(
        enabled=True,
        chains=3,
        master_seed=987,
        initialization={
            "strategy": "explicit",
            "explicit_starts": [{"mu": 1.0}, {"mu": 2.0}, {"mu": 3.0}],
            "max_attempts": 44,
        },
        pilot={
            "enabled": True,
            "nstep": 123,
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

    translated = runtime_mh._build_mh_ensemble_config(config)

    assert translated.chains == 3
    assert translated.master_seed == 987
    assert translated.initialization.strategy == "explicit"
    assert translated.initialization.explicit_starts == (
        {"mu": 1.0},
        {"mu": 2.0},
        {"mu": 3.0},
    )
    assert translated.initialization.max_attempts == 44
    assert translated.pilot.nstep == 123
    assert translated.pilot.burn_in == 0.4
    assert translated.pilot.relative_ridge == 2.0e-6
    assert translated.pilot.proposal_multiplier == 0.75
    assert translated.pilot.save_samples is True
    assert translated.diagnostics.max_rhat == 1.02
    assert translated.diagnostics.min_bulk_ess == 222.0
    assert translated.diagnostics.min_tail_ess == 111.0
    assert translated.diagnostics.require_convergence is False


def test_run_mh_ensemble_builds_fresh_stage_problems_and_pools_exploratory_run(
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

    monkeypatch.setattr(runtime_mh, "MultiChainMetropolisHastings", engine_class)
    monkeypatch.setattr(runtime_mh, "write_mh_ensemble_result", writer)
    config = MHMultichainCfg(
        enabled=True,
        chains=2,
        diagnostics={"require_convergence": False},
    )
    chain_config = MHConfig(nstep=100, burn_in=0.2, nskip=1)

    result = runtime_mh.run_mh_ensemble(
        chain_config,
        config,
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


def test_run_mh_ensemble_raises_only_after_failed_run_is_serialized(
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
        "MultiChainMetropolisHastings",
        Mock(return_value=engine),
    )
    monkeypatch.setattr(runtime_mh, "write_mh_ensemble_result", writer)
    config = MHMultichainCfg(enabled=True, chains=2)

    with pytest.raises(MHConvergenceError, match=r"mu.*preserved") as caught:
        runtime_mh.run_mh_ensemble(
            MHConfig(nstep=100, burn_in=0.2, nskip=1),
            config,
            tmp_path,
            Mock(),
        )

    assert str(tmp_path) not in str(caught.value)

    writer.assert_called_once()
    assert writer.call_args.args[0] is ensemble_result
    assert writer.call_args.args[1] == tmp_path
    assert not writer.call_args.kwargs


def test_run_mh_ensemble_rejects_disabled_configuration(tmp_path) -> None:
    with pytest.raises(ValueError, match="must be enabled"):
        runtime_mh.run_mh_ensemble(
            MHConfig(nstep=100),
            MHMultichainCfg(enabled=False),
            tmp_path,
            Mock(),
        )


def test_build_mh_config_translates_single_date_controls() -> None:
    translated = runtime_mh.build_mh_config(
        LauncherMetropolisCfg(
            nstep=321,
            burn_in=0.3,
            nskip=7,
            seed=456,
            prior_option=True,
            likelihood=False,
            monitor=True,
            display_traj=True,
        )
    )

    assert translated.nstep == 321
    assert translated.burn_in == 0.3
    assert translated.nskip == 7
    assert translated.seed == 456
    assert translated.prior_option is True
    assert translated.likelihood is False
    assert translated.monitor is True
    assert translated.display_traj is True


def test_run_mh_calibration_owns_the_single_chain_lifecycle(
    tmp_path, monkeypatch
) -> None:
    prepared_problem = object()
    samples = object()
    problem_builder = Mock(return_value=prepared_problem)
    method = SimpleNamespace(
        run=Mock(return_value=samples),
        write_calibrated_lpm=Mock(),
    )
    method_class = Mock(return_value=method)
    clear = Mock()
    monkeypatch.setattr(runtime_mh, "MetropolisHastings", method_class)
    monkeypatch.setattr(runtime_mh, "clear_mh_ensemble_artifacts", clear)
    chain_config = MHConfig(nstep=100)

    result = runtime_mh.run_mh_calibration(
        chain_config,
        None,
        tmp_path,
        problem_builder,
    )

    assert result is samples
    clear.assert_called_once_with(tmp_path)
    method_class.assert_called_once_with(config=chain_config)
    problem_builder.assert_called_once_with(tmp_path)
    method.run.assert_called_once_with(prepared_problem)
    method.write_calibrated_lpm.assert_called_once_with(samples)
