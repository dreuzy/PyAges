# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused orchestration tests for the installed single-date workflow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

import pyages.reporting.plots as workflow_plots
from pyages.config.models import MHMultichainCfg
from pyages.workflows.single_date import calibration as single_calibration
from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date


def _context(tmp_path, **overrides):
    parameters = {
        "dataset_label": None,
        "dataset_name": "audit_case.txt",
        "dataset_year": 2010,
        "dataset_data_dir": tmp_path / "data",
        "missing_error_rel": 0.01,
        "lpm_model_name": "exp",
        "directory_lpm": tmp_path / "lpm",
        "tracer_data_dir": tmp_path / "tracers",
        "run_reachable_concentrations": False,
        "reachable_concentration_nmodels": 10,
        "run_calibration_simplex": False,
        "run_calibration_metropolis_hastings": False,
        "run_objective_function": False,
        "objective_function_nmodels": 10,
        "mh_nstep": 5000,
        "mh_burn_in": 0.2,
        "mh_nskip": 10,
        "mh_seed": 12345,
        "mh_prior_option": False,
        "mh_likelihood": True,
        "mh_monitor": False,
        "mh_display_traj": False,
        "mh_multichain": None,
    }
    parameters.update(overrides)
    return SimpleNamespace(
        config_path=tmp_path / "config.yaml",
        params=SimpleNamespace(**parameters),
        output_directory=tmp_path / "results",
        observations=SimpleNamespace(
            observation_tracer_names=lambda: ["cfc11"],
            error_provenance=[],
            frame=pd.DataFrame(
                {"element": ["cfc11"], "date": [2010.0], "concentration": [1.0]}
            ),
        ),
        live_display=SimpleNamespace(),
        saved_display=SimpleNamespace(directory=tmp_path / "results"),
        plots=SimpleNamespace(
            show=Mock(), close=Mock(), close_all=Mock(), finish=Mock()
        ),
    )


@pytest.mark.parametrize(
    "multichain",
    [None, MHMultichainCfg(enabled=False)],
    ids=["absent", "disabled"],
)
def test_single_date_mh_keeps_legacy_runner_without_enabled_multichain(
    tmp_path, monkeypatch, multichain
) -> None:
    context = _context(tmp_path, mh_multichain=multichain)
    problem = object()
    samples = object()
    method = SimpleNamespace(
        method="Metropolis_Hastings",
        run=Mock(return_value=samples),
        write_calibrated_lpm=Mock(),
    )
    problem_builder = Mock(return_value=problem)
    method_class = Mock(return_value=method)
    ensemble_runner = Mock(side_effect=AssertionError("multichain must stay disabled"))
    monkeypatch.setattr(single_calibration, "_calibration_problem", problem_builder)
    monkeypatch.setattr(single_calibration, "MetropolisHastings", method_class)
    monkeypatch.setattr(
        single_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )

    result = single_calibration._run_metropolis_hastings(context)

    assert result == ("Metropolis_Hastings", samples)
    method.run.assert_called_once_with(problem)
    method.write_calibrated_lpm.assert_called_once_with(samples)
    ensemble_runner.assert_not_called()


def test_single_date_enabled_multichain_delegates_with_a_fresh_problem_builder(
    tmp_path, monkeypatch
) -> None:
    multichain = MHMultichainCfg(
        enabled=True,
        chains=2,
        diagnostics={"require_convergence": False},
    )
    context = _context(tmp_path, mh_multichain=multichain)
    created_problems: list[SimpleNamespace] = []

    def build_problem(_context, directory):
        problem = SimpleNamespace(directory=directory)
        created_problems.append(problem)
        return problem

    pooled = object()

    def run(_chain_config, _multichain, output_directory, problem_builder):
        problem_builder(output_directory / "initialization")
        problem_builder(output_directory / "chains" / "chain_001")
        return pooled

    ensemble_runner = Mock(side_effect=run)
    monkeypatch.setattr(single_calibration, "_calibration_problem", build_problem)
    monkeypatch.setattr(
        single_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )

    result = single_calibration._run_metropolis_hastings(context)

    assert result == ("Metropolis_Hastings", pooled)
    assert len({id(problem) for problem in created_problems}) == 2
    output = context.output_directory / "Metropolis_Hastings"
    assert [problem.directory for problem in created_problems] == [
        output / "initialization",
        output / "chains" / "chain_001",
    ]
    ensemble_runner.assert_called_once()
    assert ensemble_runner.call_args.args[1] is multichain
    assert ensemble_runner.call_args.args[2] == output


def test_single_date_propagates_multichain_qualification_failure(
    tmp_path, monkeypatch
) -> None:
    context = _context(
        tmp_path,
        mh_multichain=MHMultichainCfg(enabled=True, chains=2),
    )
    from pyages.calibration.methods.mh import MHConvergenceError

    failure = MHConvergenceError("mu did not converge; artifacts preserved")
    ensemble_runner = Mock(side_effect=failure)
    monkeypatch.setattr(
        single_calibration,
        "run_mh_ensemble",
        ensemble_runner,
    )

    with pytest.raises(MHConvergenceError, match=r"mu.*preserved"):
        single_calibration._run_metropolis_hastings(context)

    ensemble_runner.assert_called_once()


def test_run_calibrations_respects_independent_enable_flags(
    tmp_path, monkeypatch
) -> None:
    context = _context(
        tmp_path,
        run_calibration_simplex=True,
        run_calibration_metropolis_hastings=True,
    )
    simplex_result = object()
    mh_result = object()
    monkeypatch.setattr(
        single_calibration,
        "_run_simplex",
        lambda _context: ("Simplex", simplex_result),
    )
    monkeypatch.setattr(
        single_calibration,
        "_run_metropolis_hastings",
        lambda _context: ("Metropolis_Hastings", mh_result),
    )

    assert single_calibration.run_calibrations(context) == {
        "Simplex": simplex_result,
        "Metropolis_Hastings": mh_result,
    }
    assert single_calibration.run_calibrations(_context(tmp_path)) == {}


def test_case_label_prefers_explicit_label_and_normalizes_filename() -> None:
    assert (
        single_reporting.case_label(
            SimpleNamespace(dataset_label="Published case", dataset_name="ignored.txt")
        )
        == "Published case"
    )
    assert (
        single_reporting.case_label(
            SimpleNamespace(dataset_label=None, dataset_name="audit_case.txt")
        )
        == "audit case"
    )


def test_render_summary_writes_model_space_and_parameter_figures(
    tmp_path, monkeypatch
) -> None:
    context = _context(tmp_path)
    context.output_directory.mkdir()
    model_space_figure = object()
    parameter_figure = object()
    model_space = Mock(return_value=model_space_figure)
    parameters = Mock(return_value=parameter_figure)
    monkeypatch.setattr(workflow_plots, "plot_single_date_model_space", model_space)
    monkeypatch.setattr(workflow_plots, "plot_parameter_summary", parameters)
    posterior = SimpleNamespace(get_param_names=lambda: ["mu"])
    reachable = pd.DataFrame({"cfc11": [1.0]})

    single_reporting.render_summary(context, reachable, {"MH": posterior})

    model_space.assert_called_once()
    assert model_space.call_args.kwargs["filename"].name == "01_data_model_space.png"
    parameters.assert_called_once()
    assert parameters.call_args.kwargs["param_names"] == ["mu"]
    assert parameters.call_args.kwargs["filename"].name == "02_parameter_summary.png"
    assert context.plots.show.call_count == 2
    assert context.plots.close.call_args_list[0].args == (model_space_figure,)
    assert context.plots.close.call_args_list[1].args == (parameter_figure,)


def test_render_summary_is_a_noop_without_calibrations(tmp_path) -> None:
    context = _context(tmp_path)

    single_reporting.render_summary(context, pd.DataFrame(), {})

    context.plots.show.assert_not_called()
    context.plots.close.assert_not_called()


def test_objective_analysis_builds_table_and_figure(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path, run_objective_function=True)
    context.output_directory.mkdir()
    objective = pd.DataFrame({"mu": [1.0, 2.0], "obj_function": [3.0, 4.0]})
    sampling = SimpleNamespace(
        compute_concentrations=Mock(),
        objective_function_build=Mock(),
        objective_function_frame=lambda: objective,
        parameter_names=lambda: ["mu"],
    )
    sampling_class = Mock(return_value=sampling)
    figure = object()
    plot = Mock(return_value=figure)
    monkeypatch.setattr(single_reporting, "SystematicSampling", sampling_class)
    monkeypatch.setattr(workflow_plots, "plot_objective_summary", plot)

    single_reporting.run_objective_analysis(context, {"MH": object()})

    sampling.compute_concentrations.assert_called_once_with()
    sampling.objective_function_build.assert_called_once_with()
    written = pd.read_table(context.output_directory / "objective_function_grid.txt")
    pd.testing.assert_frame_equal(written, objective)
    assert plot.call_args.kwargs["param_names"] == ["mu"]
    context.plots.show.assert_called_once_with()
    context.plots.close.assert_called_once_with(figure)


def test_concentration_output_builds_model_and_exports_result_directory(
    tmp_path, monkeypatch
) -> None:
    context = _context(tmp_path)
    model = object()
    build = Mock(return_value=model)
    export = Mock()
    monkeypatch.setattr(single_reporting, "build_lpm", build)
    monkeypatch.setattr(single_reporting, "export_concentration_chronicles", export)

    single_reporting.write_concentration_outputs(context)

    build.assert_called_once_with("exp", directory_lpm=context.params.directory_lpm)
    export.assert_called_once_with(
        [context.output_directory],
        model,
        context.saved_display,
        tracer_data_dir=context.params.tracer_data_dir,
    )


def test_run_single_date_orchestrates_steps_and_manifest(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    context.output_directory.mkdir()
    calibrated = {"Simplex": object(), "Metropolis_Hastings": object()}
    reachable = pd.DataFrame({"cfc11": [1.0]})
    render = Mock()
    objective = Mock()
    concentration_outputs = Mock()
    manifest = Mock()
    monkeypatch.setattr(
        single_date, "prepare_context", lambda *_args, **_kwargs: context
    )
    monkeypatch.setattr(single_date, "reachable_concentrations", lambda _ctx: reachable)
    monkeypatch.setattr(single_date, "run_calibrations", lambda _ctx: calibrated)
    monkeypatch.setattr(single_date, "render_summary", render)
    monkeypatch.setattr(single_date, "run_objective_analysis", objective)
    monkeypatch.setattr(
        single_date, "write_concentration_outputs", concentration_outputs
    )
    monkeypatch.setattr(single_date, "write_result_manifest", manifest)

    result = single_date.run_single_date(context.config_path, force_inline=True)

    assert result == context.output_directory
    render.assert_called_once_with(context, reachable, calibrated)
    objective.assert_called_once_with(context, calibrated)
    concentration_outputs.assert_called_once_with(context)
    context.plots.finish.assert_called_once_with()
    context.plots.close_all.assert_not_called()
    assert manifest.call_args.kwargs["details"]["dataset_year"] == 2010
    assert manifest.call_args.kwargs["details"]["observation_error_policy"] == {
        "missing_error_rel": 0.01,
        "transformations": [],
    }
    assert manifest.call_args.kwargs["details"]["calibrations"] == [
        "Metropolis_Hastings",
        "Simplex",
    ]


def test_run_single_date_requires_a_configuration_path() -> None:
    try:
        single_date.run_single_date(None)
    except ValueError as error:
        assert "params_path is required" in str(error)
    else:
        raise AssertionError("run_single_date(None) must fail")


def test_run_single_date_closes_figures_and_keeps_manifest_absent_on_failure(
    tmp_path, monkeypatch
) -> None:
    context = _context(tmp_path)
    context.output_directory.mkdir()
    manifest = Mock()
    monkeypatch.setattr(
        single_date, "prepare_context", lambda *_args, **_kwargs: context
    )
    monkeypatch.setattr(
        single_date,
        "reachable_concentrations",
        Mock(side_effect=RuntimeError("calculation failed")),
    )
    monkeypatch.setattr(single_date, "write_result_manifest", manifest)

    with pytest.raises(RuntimeError, match="calculation failed"):
        single_date.run_single_date(context.config_path)

    context.plots.close_all.assert_called_once_with()
    context.plots.finish.assert_not_called()
    manifest.assert_not_called()


def test_run_single_date_manifests_a_multichain_convergence_failure(
    tmp_path, monkeypatch
) -> None:
    from pyages.calibration.methods.mh import MHConvergenceError

    context = _context(tmp_path, run_calibration_metropolis_hastings=True)
    context.output_directory.mkdir()
    error = MHConvergenceError("mu did not converge; artifacts preserved")
    success_manifest = Mock()
    failure_manifest = Mock()
    monkeypatch.setattr(
        single_date, "prepare_context", lambda *_args, **_kwargs: context
    )
    monkeypatch.setattr(single_date, "reachable_concentrations", lambda _ctx: None)
    monkeypatch.setattr(single_date, "run_calibrations", Mock(side_effect=error))
    monkeypatch.setattr(single_date, "write_result_manifest", success_manifest)
    monkeypatch.setattr(single_date, "write_failure_manifest", failure_manifest)

    with pytest.raises(MHConvergenceError, match=r"mu.*preserved"):
        single_date.run_single_date(context.config_path)

    success_manifest.assert_not_called()
    assert failure_manifest.call_args.kwargs["error"] is error
    assert failure_manifest.call_args.kwargs["details"]["calibrations"] == []
    assert failure_manifest.call_args.kwargs["details"]["calibrations_attempted"] == [
        "Metropolis_Hastings"
    ]
    assert error.__notes__ == [f"Preserved result evidence: {context.output_directory}"]
    context.plots.close_all.assert_called_once_with()
    context.plots.finish.assert_not_called()


def test_prepare_context_does_not_stage_when_observations_cannot_be_loaded(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "results"
    session = SimpleNamespace(close_all=Mock())
    params = SimpleNamespace(
        dataset_name="case.txt",
        verbose=False,
        results_use_default=False,
        results_directory=tmp_path / "custom-results",
        results_study_name="audit",
    )
    begin = Mock()
    results_directory = Mock(return_value=output)
    monkeypatch.setattr(single_context, "configuration_root", lambda _path: tmp_path)
    monkeypatch.setattr(single_context, "load_params", lambda *_args: params)
    monkeypatch.setattr(
        single_context,
        "dataset_results_directory",
        results_directory,
    )
    begin.return_value = SimpleNamespace(working_directory=output)
    monkeypatch.setattr(single_context, "begin_staged_result_run", begin)
    monkeypatch.setattr(single_context.PlotSession, "start", lambda **_kwargs: session)
    monkeypatch.setattr(
        single_context,
        "_load_observations",
        Mock(side_effect=FileNotFoundError("missing observations")),
    )

    with pytest.raises(FileNotFoundError, match="missing observations"):
        single_context.prepare_context(tmp_path / "config.yaml", force_inline=False)

    begin.assert_not_called()
    results_directory.assert_called_once_with(
        "case.txt",
        use_default=False,
        directory=tmp_path / "custom-results",
        study_name="audit",
    )
    session.close_all.assert_called_once_with()


def test_failure_manifest_keeps_a_completed_simplex_before_mh_rejection(
    tmp_path, monkeypatch
) -> None:
    from pyages.calibration.methods.mh import MHConvergenceError

    context = _context(
        tmp_path,
        run_calibration_simplex=True,
        run_calibration_metropolis_hastings=True,
    )
    context.output_directory.mkdir()
    error = MHConvergenceError("MH convergence gate rejected the chains")
    failure_manifest = Mock()
    monkeypatch.setattr(
        single_date, "prepare_context", lambda *_args, **_kwargs: context
    )
    monkeypatch.setattr(single_date, "reachable_concentrations", lambda _ctx: None)
    monkeypatch.setattr(single_date, "run_calibrations", Mock(side_effect=error))
    monkeypatch.setattr(single_date, "write_failure_manifest", failure_manifest)

    with pytest.raises(MHConvergenceError):
        single_date.run_single_date(context.config_path)

    assert failure_manifest.call_args.kwargs["details"]["calibrations"] == ["Simplex"]
    assert failure_manifest.call_args.kwargs["details"]["calibrations_attempted"] == [
        "Metropolis_Hastings"
    ]
