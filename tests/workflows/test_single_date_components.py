# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused orchestration tests for the installed single-date workflow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

import pyages.workflows.plots as workflow_plots
from pyages.workflows import single_date


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
        plots=SimpleNamespace(show=Mock(), close=Mock(), finish=Mock()),
    )


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
        single_date, "_run_simplex", lambda _context: ("Simplex", simplex_result)
    )
    monkeypatch.setattr(
        single_date,
        "_run_metropolis_hastings",
        lambda _context: ("Metropolis_Hastings", mh_result),
    )

    assert single_date._run_calibrations(context) == {
        "Simplex": simplex_result,
        "Metropolis_Hastings": mh_result,
    }
    assert single_date._run_calibrations(_context(tmp_path)) == {}


def test_case_label_prefers_explicit_label_and_normalizes_filename() -> None:
    assert (
        single_date._case_label(
            SimpleNamespace(dataset_label="Published case", dataset_name="ignored.txt")
        )
        == "Published case"
    )
    assert (
        single_date._case_label(
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

    single_date._render_summary(context, reachable, {"MH": posterior})

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

    single_date._render_summary(context, pd.DataFrame(), {})

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
    monkeypatch.setattr(single_date, "SystematicSampling", sampling_class)
    monkeypatch.setattr(workflow_plots, "plot_objective_summary", plot)

    single_date._run_objective_analysis(context, {"MH": object()})

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
    monkeypatch.setattr(single_date, "build_lpm", build)
    monkeypatch.setattr(single_date, "export_concentration_chronicles", export)

    single_date._write_concentration_outputs(context)

    build.assert_called_once_with("exp", directory_lpm=context.params.directory_lpm)
    export.assert_called_once_with(
        [context.output_directory], model, context.saved_display
    )


def test_run_single_date_orchestrates_steps_and_manifest(tmp_path, monkeypatch) -> None:
    context = _context(tmp_path)
    context.output_directory.mkdir()
    calibrated = {"Simplex": object(), "Metropolis_Hastings": object()}
    reachable = pd.DataFrame({"cfc11": [1.0]})
    render = Mock()
    objective = Mock()
    concentration_outputs = Mock()
    begin = Mock()
    manifest = Mock()
    monkeypatch.setattr(
        single_date, "_prepare_context", lambda *_args, **_kwargs: context
    )
    monkeypatch.setattr(
        single_date, "_reachable_concentrations", lambda _ctx: reachable
    )
    monkeypatch.setattr(single_date, "_run_calibrations", lambda _ctx: calibrated)
    monkeypatch.setattr(single_date, "_render_summary", render)
    monkeypatch.setattr(single_date, "_run_objective_analysis", objective)
    monkeypatch.setattr(
        single_date, "_write_concentration_outputs", concentration_outputs
    )
    monkeypatch.setattr(single_date, "begin_result_run", begin)
    monkeypatch.setattr(single_date, "write_result_manifest", manifest)

    result = single_date.run_single_date(context.config_path, force_inline=True)

    assert result == context.output_directory
    render.assert_called_once_with(context, reachable, calibrated)
    objective.assert_called_once_with(context, calibrated)
    concentration_outputs.assert_called_once_with(context)
    begin.assert_called_once_with(context.output_directory)
    context.plots.finish.assert_called_once_with()
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
