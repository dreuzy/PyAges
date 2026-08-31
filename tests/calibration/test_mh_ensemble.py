# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Integration contracts for multi-chain Metropolis--Hastings orchestration."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyages.calibration.methods.mh import ensemble as ensemble_module
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble import MultiChainMetropolisHastings
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
    build_seed_plan,
)
from pyages.calibration.methods.mh.errors import (
    MHConvergenceError,
    MHDiagnosticsUnavailableError,
)
from pyages.calibration.methods.mh.results import (
    DIAGNOSTICS_UNAVAILABLE,
    NOT_QUALIFIED,
    QUALIFIED,
)
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.config.paths import DIRECTORY_LPM_DATA, DIRECTORY_TRACER_DATA
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm


@pytest.fixture
def exp_problem_factory(
    tmp_path: Path,
) -> tuple[
    Callable[[str, int], CalibrationProblem],
    list[tuple[str, int, CalibrationProblem]],
]:
    """Return a recording factory of fresh one-parameter calibration problems."""
    target = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)
    calls: list[tuple[str, int, CalibrationProblem]] = []

    def factory(stage: str, chain_id: int) -> CalibrationProblem:
        display = DisplayOptions()
        display.figure = False
        display.text = False
        display.directory = tmp_path / stage / f"chain_{chain_id:03d}"
        problem = CalibrationProblem(
            observations,
            "exp",
            display_options=display,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()
        calls.append((stage, chain_id, problem))
        return problem

    return factory, calls


def _chain_config(*, nstep: int = 20) -> MHConfig:
    """Build a short, reproducible production configuration."""
    return MHConfig(
        nstep=nstep,
        burn_in=0.0,
        nskip=1,
        prior_option=True,
        prior_type="parametric",
        likelihood=True,
        monitor=False,
        display_traj=False,
        display_text=False,
        componentwise_source="model",
    )


def _ensemble_config(
    *,
    master_seed: int = 20260830,
    pilot: bool,
    qualified: bool = True,
) -> MHEnsembleConfig:
    """Build two explicitly dispersed chains with selectable qualification."""
    diagnostics = (
        MHDiagnosticsConfig(
            max_rhat=1.0e12,
            min_bulk_ess=1.0e-6,
            min_tail_ess=1.0e-6,
        )
        if qualified
        else MHDiagnosticsConfig(
            max_rhat=1.000001,
            min_bulk_ess=1.0e9,
            min_tail_ess=1.0e9,
            require_convergence=False,
        )
    )
    return MHEnsembleConfig(
        chains=2,
        master_seed=master_seed,
        initialization=MHInitializationConfig(
            strategy="explicit",
            explicit_starts=({"mu": 8.0}, {"mu": 12.0}),
        ),
        pilot=MHPilotConfig(
            enabled=pilot,
            nstep=18,
            burn_in=0.0,
            relative_ridge=1.0e-6,
            save_samples=True,
        ),
        diagnostics=diagnostics,
    )


def test_pilot_uses_fresh_problems_and_freezes_one_production_covariance(
    exp_problem_factory,
    monkeypatch,
) -> None:
    factory, calls = exp_problem_factory
    constructed_configs: list[MHConfig] = []
    sampler_class = ensemble_module.MetropolisHastings

    class RecordingMetropolisHastings(sampler_class):
        def __init__(self, config: MHConfig) -> None:
            constructed_configs.append(config)
            super().__init__(config)

    monkeypatch.setattr(
        ensemble_module,
        "MetropolisHastings",
        RecordingMetropolisHastings,
    )
    result = MultiChainMetropolisHastings(
        _chain_config(), _ensemble_config(pilot=True)
    ).run(factory)

    assert [(stage, chain_id) for stage, chain_id, _ in calls] == [
        ("initialization", 0),
        ("pilot", 1),
        ("pilot", 2),
        ("production", 1),
        ("production", 2),
    ]
    assert len({id(problem) for _, _, problem in calls}) == len(calls)
    assert result.pilot is not None
    assert result.pilot.samples is not None
    assert result.pilot.initial_states == ({"mu": 8.0}, {"mu": 12.0})
    assert np.linalg.eigvalsh(result.pilot.covariance)[0] > 0.0

    pilot_configs = constructed_configs[:2]
    production_configs = constructed_configs[2:]
    assert all(config.proposal_kind == "componentwise" for config in pilot_configs)
    assert all(config.proposal_kind == "correlated" for config in production_configs)
    for config in production_configs:
        np.testing.assert_allclose(config.proposal_covariance, result.pilot.covariance)
        assert config.proposal_multiplier == result.pilot.proposal_multiplier
    assert (
        production_configs[0].proposal_covariance
        == production_configs[1].proposal_covariance
    )
    assert result.chains[0].seed != result.chains[1].seed
    assert result.seed_plan == build_seed_plan(_ensemble_config(pilot=True))
    assert result.target_signature_version == 1
    assert len(result.target_sha256) == 64
    assert not result.chains[0].samples.frame.equals(result.chains[1].samples.frame)

    assert result.qualification_status == QUALIFIED
    assert {item.parameter for item in result.diagnostics} == {
        "mu",
        "mean",
        "std",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
    }
    assert all(item.qualified for item in result.diagnostics)
    assert len(result.pooled_samples().frame) == sum(
        len(chain.samples.frame) for chain in result.chains
    )


def test_no_pilot_replays_each_distinct_production_stream(
    exp_problem_factory,
) -> None:
    first_factory, first_calls = exp_problem_factory
    config = _ensemble_config(master_seed=77123, pilot=False)
    first = MultiChainMetropolisHastings(_chain_config(), config).run(first_factory)

    observations = first_calls[0][2].observations
    replay_calls: list[CalibrationProblem] = []

    def replay_factory(stage: str, chain_id: int) -> CalibrationProblem:
        problem = CalibrationProblem(
            observations,
            "exp",
            explore_objective=False,
            explore_reachable=False,
        ).prepare()
        replay_calls.append(problem)
        return problem

    replay = MultiChainMetropolisHastings(_chain_config(), config).run(replay_factory)

    assert first.pilot is None
    assert replay.pilot is None
    assert len(first_calls) == len(replay_calls) == 3
    assert first.chains[0].seed != first.chains[1].seed
    assert tuple(chain.seed for chain in first.chains) == tuple(
        chain.seed for chain in replay.chains
    )
    for first_chain, replay_chain in zip(first.chains, replay.chains, strict=True):
        pd.testing.assert_frame_equal(
            first_chain.samples.frame,
            replay_chain.samples.frame,
            check_exact=True,
        )
    assert not first.chains[0].samples.frame.equals(first.chains[1].samples.frame)
    assert first.seed_plan == replay.seed_plan == build_seed_plan(config)
    assert first.target_sha256 == replay.target_sha256


def test_pilot_run_is_fully_replayable_from_the_master_seed(
    exp_problem_factory,
) -> None:
    factory, _calls = exp_problem_factory
    config = _ensemble_config(master_seed=99173, pilot=True)

    first = MultiChainMetropolisHastings(_chain_config(), config).run(factory)
    replay = MultiChainMetropolisHastings(_chain_config(), config).run(factory)

    assert first.seed_plan == replay.seed_plan == build_seed_plan(config)
    assert first.target_sha256 == replay.target_sha256
    assert first.pilot is not None
    assert replay.pilot is not None
    assert first.pilot.initial_states == replay.pilot.initial_states
    assert first.pilot.final_states == replay.pilot.final_states
    np.testing.assert_array_equal(first.pilot.covariance, replay.pilot.covariance)
    assert first.pilot.proposal_multiplier == replay.pilot.proposal_multiplier
    assert first.pilot.acceptance_rates == replay.pilot.acceptance_rates
    assert first.pilot.retained_counts == replay.pilot.retained_counts
    assert first.pilot.samples is not None
    assert replay.pilot.samples is not None
    for first_samples, replay_samples in zip(
        first.pilot.samples,
        replay.pilot.samples,
        strict=True,
    ):
        np.testing.assert_array_equal(first_samples, replay_samples)
    for first_chain, replay_chain in zip(first.chains, replay.chains, strict=True):
        assert first_chain.seed == replay_chain.seed
        assert first_chain.initial_params == replay_chain.initial_params
        pd.testing.assert_frame_equal(
            first_chain.samples.frame,
            replay_chain.samples.frame,
            check_exact=True,
        )


def test_nonqualified_ensemble_refuses_qualified_pooling(
    exp_problem_factory,
) -> None:
    factory, _ = exp_problem_factory
    result = MultiChainMetropolisHastings(
        _chain_config(), _ensemble_config(pilot=False, qualified=False)
    ).run(factory)

    assert result.qualification_status == NOT_QUALIFIED
    assert any(not item.qualified for item in result.diagnostics)
    with pytest.raises(RuntimeError, match="cannot be pooled as qualified"):
        result.pooled_samples()
    assert len(result.pooled_samples(require_qualified=False).frame) == 38


def test_constant_derived_moment_does_not_make_qualification_impossible() -> None:
    target = build_lpm("dirac")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)

    def factory(_stage: str, _chain_id: int) -> CalibrationProblem:
        return CalibrationProblem(
            observations,
            "dirac",
            explore_objective=False,
            explore_reachable=False,
        ).prepare()

    config = MHEnsembleConfig(
        chains=2,
        master_seed=8102,
        initialization=MHInitializationConfig(
            strategy="explicit",
            explicit_starts=({"mu": 8.0}, {"mu": 12.0}),
        ),
        pilot=MHPilotConfig(enabled=False),
        diagnostics=MHDiagnosticsConfig(
            max_rhat=1.0e12,
            min_bulk_ess=1.0e-6,
            min_tail_ess=1.0e-6,
        ),
    )

    result = MultiChainMetropolisHastings(_chain_config(), config).run(factory)

    std_diagnostic = next(
        item for item in result.diagnostics if item.parameter == "std"
    )
    assert not std_diagnostic.included_in_qualification
    assert not std_diagnostic.qualified
    assert result.qualification_status == QUALIFIED


def test_factory_reusing_the_same_problem_is_rejected() -> None:
    target = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)
    problem = CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()

    with pytest.raises(ValueError, match="fresh CalibrationProblem"):
        MultiChainMetropolisHastings(
            _chain_config(), _ensemble_config(pilot=False)
        ).run(lambda stage, chain_id: problem)


def test_required_ess_threshold_must_be_reachable_from_retained_draws() -> None:
    config = MHEnsembleConfig(
        chains=2,
        initialization=MHInitializationConfig(strategy="model_default"),
        pilot=MHPilotConfig(enabled=False),
        diagnostics=MHDiagnosticsConfig(
            min_bulk_ess=100.0,
            min_tail_ess=100.0,
            require_convergence=True,
        ),
    )

    with pytest.raises(ValueError, match="maximum split-draw ESS"):
        MultiChainMetropolisHastings(_chain_config(nstep=20), config)


@pytest.mark.parametrize(
    ("override", "option"),
    [
        ({"monitor": True}, "monitor"),
        ({"display_traj": True}, "display_traj"),
    ],
)
def test_ensemble_rejects_one_chain_trajectory_options(override, option) -> None:
    chain_config = replace(_chain_config(), **override)

    with pytest.raises(ValueError, match=option):
        MultiChainMetropolisHastings(
            chain_config,
            _ensemble_config(pilot=False),
        )


def test_ensemble_preserves_text_summary_option() -> None:
    chain_config = MHConfig(
        nstep=20,
        burn_in=0.0,
        nskip=1,
        prior_option=True,
        monitor=False,
        display_traj=False,
        display_text=True,
        componentwise_source="model",
    )
    runner = MultiChainMetropolisHastings(
        chain_config,
        _ensemble_config(pilot=False),
    )

    production = runner._production_config(
        initial_params={"mu": 10.0},
        seed=7,
        pilot=None,
    )

    assert not production.monitor
    assert not production.display_traj
    assert production.display_text


def test_pilot_requires_componentwise_adaptation_but_disabled_pilot_does_not(
    exp_problem_factory,
) -> None:
    factory, _calls = exp_problem_factory
    correlated = replace(
        _chain_config(),
        proposal_kind="correlated",
        proposal_covariance=((1.0,),),
    )

    with pytest.raises(ValueError, match="requires proposal_kind='componentwise'"):
        MultiChainMetropolisHastings(
            correlated,
            _ensemble_config(pilot=True),
        )

    result = MultiChainMetropolisHastings(
        correlated,
        _ensemble_config(pilot=False),
    ).run(factory)
    assert result.pilot is None
    assert len(result.chains) == 2


@pytest.mark.parametrize(
    ("variation", "category"),
    [
        ("observation", "observations"),
        ("observation_order", "observations"),
        ("lpm", "lpm"),
        ("tracer_grid", "tracer_grids"),
    ],
)
def test_scientific_target_drift_is_rejected_before_any_sampling(
    variation: str,
    category: str,
    monkeypatch,
) -> None:
    target = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11", "kr85"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)
    baseline_frame = observations.frame.copy()

    def factory(stage: str, chain_id: int) -> CalibrationProblem:
        frame = baseline_frame.copy()
        model_name = "exp"
        divergent = stage == "production" and chain_id == 2
        if divergent and variation == "observation":
            frame.loc[0, "concentration"] *= 1.01
        elif divergent and variation == "observation_order":
            frame = frame.iloc[::-1].reset_index(drop=True)
        elif divergent and variation == "lpm":
            model_name = "dirac"
        problem = CalibrationProblem(
            Concentrations.from_dataframe(frame),
            model_name,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()
        if divergent and variation == "tracer_grid":
            convolution = problem.tracers.convolutions[0]
            grid = convolution.prepared_grid
            assert grid is not None
            changed_midpoints = np.array(grid.k_mid, copy=True)
            changed_midpoints[0] = np.nextafter(changed_midpoints[0], np.inf)
            convolution._prepared_grid = replace(  # noqa: SLF001
                grid,
                k_mid=changed_midpoints,
            )
        return problem

    def unexpected_sampling(*_args, **_kwargs):
        raise AssertionError("sampling started before target preflight completed")

    monkeypatch.setattr(MultiChainMetropolisHastings, "_diagnose", unexpected_sampling)
    monkeypatch.setattr(
        ensemble_module.MetropolisHastings,
        "run",
        unexpected_sampling,
    )

    with pytest.raises(
        ValueError,
        match=(f"stage='production', chain_id=2, category='{category}'"),
    ):
        MultiChainMetropolisHastings(
            _chain_config(),
            _ensemble_config(pilot=False),
        ).run(factory)


def test_direct_tracer_content_drift_is_rejected_without_a_prepared_grid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_root = tmp_path / "baseline_tracers"
    divergent_root = tmp_path / "divergent_tracers"
    shutil.copytree(DIRECTORY_TRACER_DATA / "cfc11", baseline_root / "cfc11")
    shutil.copytree(DIRECTORY_TRACER_DATA / "cfc11", divergent_root / "cfc11")
    divergent_chronicle = divergent_root / "cfc11" / "recharge.csv"
    divergent_frame = pd.read_csv(divergent_chronicle, comment="#")
    row = len(divergent_frame) // 2
    divergent_frame.loc[row, "concentration"] = np.nextafter(
        divergent_frame.loc[row, "concentration"],
        np.inf,
    )
    divergent_frame.to_csv(divergent_chronicle, index=False)

    target = build_lpm("dirac")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)
    prepared_grids: list[object | None] = []

    def factory(stage: str, chain_id: int) -> CalibrationProblem:
        tracer_root = (
            divergent_root if stage == "production" and chain_id == 2 else baseline_root
        )
        problem = CalibrationProblem(
            Concentrations.from_dataframe(observations.frame),
            "dirac",
            tracer_data_directory=tracer_root,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()
        prepared_grids.append(problem.tracers.convolutions[0].prepared_grid)
        return problem

    def unexpected_sampling(*_args, **_kwargs):
        raise AssertionError("sampling started before direct-tracer preflight")

    monkeypatch.setattr(
        ensemble_module.MetropolisHastings,
        "run",
        unexpected_sampling,
    )

    with pytest.raises(
        ValueError,
        match=("stage='production', chain_id=2, category='tracer_grids'"),
    ):
        MultiChainMetropolisHastings(
            _chain_config(),
            _ensemble_config(pilot=False),
        ).run(factory)

    assert prepared_grids
    assert all(grid is None for grid in prepared_grids)


def test_shapefree_document_drift_is_rejected_before_any_sampling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_root = tmp_path / "baseline_lpms"
    divergent_root = tmp_path / "divergent_lpms"
    source = DIRECTORY_LPM_DATA / "shapefree_n_oldbin"
    shutil.copytree(source, baseline_root / "shapefree_n_oldbin")
    shutil.copytree(source, divergent_root / "shapefree_n_oldbin")
    divergent_path = divergent_root / "shapefree_n_oldbin" / "params.yaml"
    divergent_document = yaml.safe_load(divergent_path.read_text(encoding="utf-8"))
    divergent_document["shapefree"]["edges"][1] = 25.0
    divergent_path.write_text(
        yaml.safe_dump(divergent_document, sort_keys=False),
        encoding="utf-8",
    )

    target = build_lpm("shapefree_n_oldbin", baseline_root)
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.20)

    def factory(stage: str, chain_id: int) -> CalibrationProblem:
        lpm_root = (
            divergent_root if stage == "production" and chain_id == 2 else baseline_root
        )
        return CalibrationProblem(
            Concentrations.from_dataframe(observations.frame),
            "shapefree_n_oldbin",
            lpm_directory=lpm_root,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()

    def unexpected_sampling(*_args, **_kwargs):
        raise AssertionError("sampling started before shape-free target preflight")

    monkeypatch.setattr(
        ensemble_module.MetropolisHastings,
        "run",
        unexpected_sampling,
    )
    ensemble_config = MHEnsembleConfig(
        chains=2,
        master_seed=7654,
        initialization=MHInitializationConfig(
            strategy="explicit",
            explicit_starts=(
                {"z1": -1.0, "z2": 0.0, "z3": 1.0},
                {"z1": 1.0, "z2": 0.0, "z3": -1.0},
            ),
        ),
        pilot=MHPilotConfig(enabled=False),
        diagnostics=MHDiagnosticsConfig(require_convergence=False),
    )

    with pytest.raises(
        ValueError,
        match="stage='production', chain_id=2, category='lpm'",
    ):
        MultiChainMetropolisHastings(
            _chain_config(),
            ensemble_config,
        ).run(factory)


def test_too_few_production_draws_are_rejected_before_running() -> None:
    config = _ensemble_config(pilot=False)

    with pytest.raises(ValueError, match="at least eight draws"):
        MultiChainMetropolisHastings(_chain_config(nstep=8), config)


def test_unavailable_diagnostics_preserve_completed_chain_results(
    exp_problem_factory,
    monkeypatch,
) -> None:
    factory, _calls = exp_problem_factory
    runner = MultiChainMetropolisHastings(
        _chain_config(),
        _ensemble_config(pilot=False),
    )

    def fail_diagnostics(_chains):
        raise MHDiagnosticsUnavailableError("derived quantity is non-finite")

    monkeypatch.setattr(runner, "_diagnose", fail_diagnostics)

    result = runner.run(factory)

    assert len(result.chains) == 2
    assert result.diagnostics == ()
    assert result.qualification_status == DIAGNOSTICS_UNAVAILABLE
    assert result.diagnostics_message == "derived quantity is non-finite"
    with pytest.raises(MHConvergenceError, match="diagnostics_unavailable"):
        result.pooled_samples()


def test_unexpected_diagnostic_value_error_is_not_reclassified(
    exp_problem_factory,
    monkeypatch,
) -> None:
    factory, _calls = exp_problem_factory
    runner = MultiChainMetropolisHastings(
        _chain_config(),
        _ensemble_config(pilot=False),
    )

    def fail_diagnostics(_chains):
        raise ValueError("diagnostic programming defect")

    monkeypatch.setattr(runner, "_diagnose", fail_diagnostics)

    with pytest.raises(ValueError, match="programming defect"):
        runner.run(factory)


def test_unexpected_mcse_value_error_is_not_masked(
    exp_problem_factory,
    monkeypatch,
) -> None:
    factory, _calls = exp_problem_factory
    runner = MultiChainMetropolisHastings(
        _chain_config(),
        _ensemble_config(pilot=False),
    )

    def fail_mcse(*_args, **_kwargs):
        raise ValueError("mcse programming defect")

    monkeypatch.setattr(ensemble_module, "mcse_mean", fail_mcse)

    with pytest.raises(ValueError, match="mcse programming defect"):
        runner.run(factory)
