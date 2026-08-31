# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused contracts for temporal workflow preparation and orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from pyages.config.models import (
    MHMultichainCfg,
    TemporalCalibrationCfg,
    TemporalFiguresCfg,
    TemporalResultsCfg,
)
from pyages.workflows.temporal import calibration as temporal_calibration
from pyages.workflows.temporal import cases as temporal_cases
from pyages.workflows.temporal import context as temporal_context
from pyages.workflows.temporal import runner as temporal


@pytest.mark.parametrize(
    "multichain",
    [None, MHMultichainCfg(enabled=False)],
    ids=["absent", "disabled"],
)
def test_temporal_mh_keeps_legacy_runner_without_enabled_multichain(
    tmp_path, monkeypatch, multichain
) -> None:
    prepared_problem = object()
    problem = SimpleNamespace(prepare=Mock(return_value=prepared_problem))
    problem_class = Mock(return_value=problem)
    samples = object()
    method = SimpleNamespace(
        method="Metropolis_Hastings",
        run=Mock(return_value=samples),
        write_calibrated_lpm=Mock(),
    )
    method_class = Mock(return_value=method)
    ensemble_runner = Mock(side_effect=AssertionError("multichain must stay disabled"))
    monkeypatch.setattr(temporal_calibration, "CalibrationProblem", problem_class)
    monkeypatch.setattr(temporal_calibration, "MetropolisHastings", method_class)
    monkeypatch.setattr(
        temporal_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )

    temporal_calibration.run_model_calibration(
        object(),
        "exp",
        tmp_path / "results",
        tmp_path / "lpm",
        TemporalCalibrationCfg(
            seed_enabled=True,
            seed=42,
            multichain=multichain,
        ),
        TemporalFiguresCfg(),
    )

    method.run.assert_called_once_with(prepared_problem)
    method.write_calibrated_lpm.assert_called_once_with(samples)
    ensemble_runner.assert_not_called()


def test_temporal_enabled_multichain_delegates_with_fresh_stage_problems(
    tmp_path, monkeypatch
) -> None:
    created: list[tuple[object, object]] = []

    def build_problem(*_args, display_options, **_kwargs):
        prepared = object()
        created.append((display_options.directory, prepared))
        return SimpleNamespace(prepare=Mock(return_value=prepared))

    pooled = object()

    def run(_chain_config, _multichain, output_directory, problem_builder):
        problems = [
            problem_builder(output_directory / "initialization"),
            problem_builder(output_directory / "pilot" / "chain_001"),
            problem_builder(output_directory / "chains" / "chain_001"),
        ]
        assert len({id(problem) for problem in problems}) == 3
        return pooled

    ensemble_runner = Mock(side_effect=run)
    monkeypatch.setattr(temporal_calibration, "CalibrationProblem", build_problem)
    monkeypatch.setattr(
        temporal_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )
    output = tmp_path / "results"

    temporal_calibration.run_model_calibration(
        object(),
        "exp",
        output,
        tmp_path / "lpm",
        TemporalCalibrationCfg(
            seed_enabled=True,
            seed=42,
            multichain=MHMultichainCfg(
                enabled=True,
                chains=2,
                diagnostics={"require_convergence": False},
            ),
        ),
        TemporalFiguresCfg(),
    )

    assert [Path(directory) for directory, _problem in created] == [
        output / "initialization",
        output / "pilot" / "chain_001",
        output / "chains" / "chain_001",
    ]
    assert len({id(problem) for _directory, problem in created}) == 3
    ensemble_runner.assert_called_once()
    assert ensemble_runner.call_args.args[2] == output


def test_temporal_propagates_multichain_qualification_failure(
    tmp_path, monkeypatch
) -> None:
    from pyages.calibration.methods.mh import MHConvergenceError

    ensemble_runner = Mock(
        side_effect=MHConvergenceError("mean did not converge; artifacts preserved")
    )
    monkeypatch.setattr(
        temporal_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )

    with pytest.raises(
        MHConvergenceError,
        match=r"mean.*preserved",
    ):
        temporal_calibration.run_model_calibration(
            object(),
            "exp",
            tmp_path / "results",
            tmp_path / "lpm",
            TemporalCalibrationCfg(
                mh_nsteps=5000,
                seed_enabled=True,
                seed=42,
                multichain=MHMultichainCfg(enabled=True, chains=2),
            ),
            TemporalFiguresCfg(),
        )

    ensemble_runner.assert_called_once()


def test_temporal_mh_uses_an_explicit_fresh_seed_when_fixed_seed_is_disabled(
    monkeypatch,
) -> None:
    random_seed = Mock(return_value=987654321)
    monkeypatch.setattr(temporal_calibration.secrets, "randbits", random_seed)

    config = temporal_calibration.build_mh_config(
        TemporalCalibrationCfg(seed_enabled=False)
    )

    assert config.seed == 987654321
    random_seed.assert_called_once_with(63)


def test_temporal_mh_preserves_an_enabled_fixed_seed(monkeypatch) -> None:
    random_seed = Mock(side_effect=AssertionError("fresh seed must not be requested"))
    monkeypatch.setattr(temporal_calibration.secrets, "randbits", random_seed)

    config = temporal_calibration.build_mh_config(
        TemporalCalibrationCfg(seed_enabled=True, seed=42)
    )

    assert config.seed == 42
    random_seed.assert_not_called()


def test_temporal_multichain_does_not_consume_the_legacy_seed_stream(
    monkeypatch,
) -> None:
    random_seed = Mock(side_effect=AssertionError("legacy seed must not be drawn"))
    monkeypatch.setattr(temporal_calibration.secrets, "randbits", random_seed)

    config = temporal_calibration.build_mh_config(
        TemporalCalibrationCfg(multichain={"enabled": True})
    )

    assert config.seed == 0
    random_seed.assert_not_called()


def test_successive_date_labels_preserve_close_distinct_dates() -> None:
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "element": ["cfc11", "cfc11"],
                "concentration": [1.0, 2.0],
                "error": [0.1, 0.2],
                "unit": ["pptv", "pptv"],
                "date": [2005.4300001, 2005.4300002],
            }
        )
    )

    labels = [
        label
        for label, _frame in temporal_cases.build_case_frames(
            observations, "successive"
        )
    ]

    assert labels == ["date_2005_4300001", "date_2005_4300002"]


def test_load_concentrations_resolves_errors_after_optional_override(
    tmp_path, monkeypatch
) -> None:
    dataset = tmp_path / "observations.txt"
    pd.DataFrame(
        {
            "element": ["cfc11", "cfc12"],
            "concentration": [10.0, 20.0],
            "error": [0.0, 5.0],
            "unit": ["pptv", "pptv"],
            "date": [2010.0, 2010.0],
        }
    ).to_csv(dataset, sep="\t", index=False)
    resolved = Mock()
    monkeypatch.setattr(temporal_context, "resolve_observation_errors", resolved)

    observations = temporal_context._load_concentrations(dataset, error_rel=0.2)

    assert observations.frame["error"].tolist() == [2.0, 4.0]
    resolved.assert_called_once_with(
        observations,
        missing_error_relative_fraction=0.01,
    )


def test_run_temporal_writes_effective_observations_and_manifest(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "results"
    output.mkdir()
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "element": ["cfc11"],
                "concentration": [1.0],
                "error": [0.1],
                "unit": ["pptv"],
                "date": [2010.0],
            }
        ),
        observation_tracer_names=lambda: ["cfc11"],
        error_provenance=[],
    )
    context = SimpleNamespace(
        config_path=tmp_path / "config.yaml",
        dataset_path=tmp_path / "observations.txt",
        mode="span",
        models=["exp"],
        lpm_directory=tmp_path / "lpm",
        observations=observations,
        output_directory=output,
        params=SimpleNamespace(
            dataset=SimpleNamespace(error_rel=None, missing_error_rel=0.01),
            calibration=TemporalCalibrationCfg(seed_enabled=True, seed=1),
            figures=SimpleNamespace(),
        ),
    )
    manifest = Mock()
    case_directory = output / "span_full"
    monkeypatch.setattr(temporal, "prepare_context", lambda _path: context)
    monkeypatch.setattr(
        temporal,
        "_run_temporal_cases",
        lambda *_args, **_kwargs: [case_directory],
    )
    monkeypatch.setattr(temporal, "write_result_manifest", manifest)

    result = temporal.run_temporal(context.config_path)

    assert result == case_directory
    written = pd.read_table(output / "concentrations.txt")
    pd.testing.assert_frame_equal(written, observations.frame)
    assert manifest.call_args.kwargs["input_paths"][0] == context.dataset_path
    assert manifest.call_args.kwargs["details"]["observation_error_policy"] == {
        "error_rel": None,
        "missing_error_rel": 0.01,
        "transformations": [],
    }


def test_run_temporal_manifests_a_multichain_convergence_failure(
    tmp_path, monkeypatch
) -> None:
    from pyages.calibration.methods.mh import MHConvergenceError

    output = tmp_path / "results"
    output.mkdir()
    observations = SimpleNamespace(
        frame=pd.DataFrame(
            {
                "element": ["cfc11"],
                "concentration": [1.0],
                "error": [0.1],
                "unit": ["pptv"],
                "date": [2010.0],
            }
        ),
        observation_tracer_names=lambda: ["cfc11"],
        error_provenance=[],
    )
    context = SimpleNamespace(
        config_path=tmp_path / "config.yaml",
        dataset_path=tmp_path / "observations.txt",
        mode="span",
        models=["exp"],
        lpm_directory=tmp_path / "lpm",
        observations=observations,
        output_directory=output,
        params=SimpleNamespace(
            dataset=SimpleNamespace(error_rel=None, missing_error_rel=0.01),
            calibration=TemporalCalibrationCfg(seed_enabled=True, seed=1),
            figures=SimpleNamespace(),
        ),
    )
    error = MHConvergenceError("mean did not converge; artifacts preserved")
    failure_manifest = Mock()

    def fail_after_start(*_args, written_case_directories, **_kwargs):
        written_case_directories.append(output / "span_full")
        raise error

    monkeypatch.setattr(temporal, "prepare_context", lambda _path: context)
    monkeypatch.setattr(temporal, "_run_temporal_cases", fail_after_start)
    monkeypatch.setattr(temporal, "write_failure_manifest", failure_manifest)
    success_manifest = Mock()
    monkeypatch.setattr(temporal, "write_result_manifest", success_manifest)

    with pytest.raises(MHConvergenceError, match=r"mean.*preserved"):
        temporal.run_temporal(context.config_path)

    success_manifest.assert_not_called()
    assert failure_manifest.call_args.kwargs["error"] is error
    assert failure_manifest.call_args.kwargs["details"]["case_directories"] == [
        "span_full"
    ]


def test_prepare_temporal_context_invalidates_before_missing_dataset_failure(
    tmp_path, monkeypatch
) -> None:
    config_path = tmp_path / "config.yaml"
    results_root = tmp_path / "results"
    params = SimpleNamespace(
        dataset=SimpleNamespace(file="missing.txt"),
        results=TemporalResultsCfg(
            use_default=False,
            directory=str(results_root),
            study_name="audit",
        ),
        workflow=SimpleNamespace(mode="span"),
    )
    begin = Mock()
    monkeypatch.setattr(temporal_context, "configuration_root", lambda _path: tmp_path)
    monkeypatch.setattr(
        temporal_context,
        "_load_params_validated",
        lambda _path: params,
    )
    monkeypatch.setattr(temporal_context, "begin_result_run", begin)

    with pytest.raises(FileNotFoundError, match="Dataset file not found"):
        temporal_context.prepare_context(config_path)

    expected_output = results_root / "audit" / "missing" / "span"
    begin.assert_called_once_with(expected_output)
