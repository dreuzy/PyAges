# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Behavioral tests for CLI discovery, diagnostics, and failure paths."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import pyages.cli.commands.check as check_cmd
import pyages.cli.commands.run as run_cmd
import pyages.config.paths as config_paths
import pyages.lpm.core.registry as registry
import pyages.lpm.factory as lpm_factory
import pyages.tracer.tracer_root as tracer_root
import pyages.workflows.single_date as single_date_workflow
import pyages.workflows.temporal as temporal_workflow
from pyages.cli.commands.list_cmd import list_group


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text("dataset: {}\n", encoding="utf-8")
    return path


def test_cli_lists_lpms_in_compact_and_verbose_modes(monkeypatch) -> None:
    class DescribedLpm:
        """Audited model description.

        Additional details are intentionally omitted from CLI output.
        """

    class UndocumentedLpm:
        __doc__ = None

    models = {"audit": DescribedLpm, "bare": UndocumentedLpm}
    monkeypatch.setattr(lpm_factory, "list_available_lpms", lambda: list(models))
    monkeypatch.setattr(registry, "get_lpm_class", models.__getitem__)
    runner = CliRunner()

    compact = runner.invoke(list_group, ["lpms"])
    verbose = runner.invoke(list_group, ["lpms", "--verbose"])

    assert compact.exit_code == 0
    assert "Available LPM models (2)" in compact.output
    assert "  - audit" in compact.output
    assert verbose.exit_code == 0
    assert "Audited model description." in verbose.output
    assert "No description" in verbose.output


def test_cli_lists_sorted_visible_tracers_with_verbose_metadata(
    tmp_path, monkeypatch
) -> None:
    for name in ["zeta", ".hidden", "alpha"]:
        (tmp_path / name).mkdir()

    class FakeTracer:
        def __init__(self, directory, name):
            assert directory == tmp_path
            self.unit = "TU" if name == "alpha" else "pptv"
            self.datemin = 1960.0
            self.datemax = 2020.0

    monkeypatch.setattr(config_paths, "DIRECTORY_TRACER_DATA", tmp_path)
    monkeypatch.setattr(tracer_root, "Tracer", FakeTracer)
    runner = CliRunner()

    compact = runner.invoke(list_group, ["tracers"])
    verbose = runner.invoke(list_group, ["tracers", "--verbose"])

    assert compact.exit_code == 0
    assert compact.output.index("alpha") < compact.output.index("zeta")
    assert ".hidden" not in compact.output
    assert verbose.exit_code == 0
    assert f"Location: {tmp_path}" in verbose.output
    assert "unit: TU" in verbose.output
    assert "range: 1960-2020" in verbose.output


@pytest.mark.parametrize(
    ("check_result", "exit_code", "message"),
    [
        (check_cmd.CheckResult(passed=5), 0, "All 5 checks passed"),
        (check_cmd.CheckResult(passed=3, failed=2), 1, "2/5 checks failed"),
    ],
)
def test_cli_check_reports_aggregate_status(
    check_result, exit_code, message, monkeypatch
) -> None:
    monkeypatch.setattr(check_cmd, "_run_checks", lambda verbose: check_result)

    result = CliRunner().invoke(check_cmd.check, ["--verbose"])

    assert result.exit_code == exit_code
    assert message in result.output


def test_cli_check_handles_missing_distribution_metadata(monkeypatch) -> None:
    def missing_distribution(_name):
        raise check_cmd.metadata.PackageNotFoundError("pyages")

    monkeypatch.setattr(check_cmd.metadata, "requires", missing_distribution)

    result = check_cmd._check_dependencies(verbose=False)

    assert result == check_cmd.CheckResult(failed=1)


def test_cli_check_handles_a_missing_dependency(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        check_cmd.metadata, "requires", lambda _name: ["missing-package>=1"]
    )

    def missing_version(_name):
        raise check_cmd.metadata.PackageNotFoundError("missing-package")

    monkeypatch.setattr(check_cmd.metadata, "version", missing_version)

    result = check_cmd._check_dependencies(verbose=True)

    assert result == check_cmd.CheckResult(failed=1)
    assert "missing-package not installed" in capsys.readouterr().out


def test_cli_check_registry_and_tracer_details(monkeypatch, tmp_path, capsys) -> None:
    (tmp_path / "cfc11").mkdir()
    monkeypatch.setattr(lpm_factory, "list_available_lpms", lambda: ["exp", "ig"])
    monkeypatch.setattr(config_paths, "DIRECTORY_TRACER_DATA", tmp_path)

    assert check_cmd._check_lpm_registry(verbose=True) == check_cmd.CheckResult(
        passed=1
    )
    assert check_cmd._check_tracers(verbose=True) == check_cmd.CheckResult(passed=1)
    output = capsys.readouterr().out
    assert "LPM registry: 2 models" in output
    assert "- exp" in output
    assert "Tracers: 1 found" in output
    assert "- cfc11" in output


def test_cli_check_registry_failure_is_reported(monkeypatch, capsys) -> None:
    def broken_registry():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(lpm_factory, "list_available_lpms", broken_registry)

    result = check_cmd._check_lpm_registry(verbose=False)

    assert result == check_cmd.CheckResult(failed=1)
    assert "registry unavailable" in capsys.readouterr().out


def test_cli_run_rejects_non_positive_mh_steps(tmp_path) -> None:
    result = CliRunner().invoke(
        run_cmd.run,
        [str(_config(tmp_path)), "--mh-nsteps", "0"],
    )

    assert result.exit_code == 1
    assert "Invalid CLI arguments" in result.output
    assert "mh_nsteps must be > 0" in result.output


@pytest.mark.parametrize(
    ("mode_args", "warning"),
    [
        (["--transient", "--data-name", "ignored.txt"], "single-date only"),
        (["--data-file", "ignored.txt"], "transient only"),
    ],
)
def test_cli_run_warns_about_mode_specific_overrides(
    tmp_path, mode_args, warning, monkeypatch
) -> None:
    monkeypatch.setattr(run_cmd, "_run_single_date", lambda *_args: None)
    monkeypatch.setattr(run_cmd, "_run_transient", lambda *_args: None)

    result = CliRunner().invoke(run_cmd.run, [str(_config(tmp_path)), *mode_args])

    assert result.exit_code == 0
    assert warning in result.output


def test_cli_run_removes_temporary_override_after_dispatch_failure(
    tmp_path, monkeypatch
) -> None:
    dispatched = {}

    def fail(config, inline, verbose):
        del inline, verbose
        dispatched["config"] = Path(config)
        raise RuntimeError("workflow failed")

    monkeypatch.setattr(run_cmd, "_run_single_date", fail)

    result = CliRunner().invoke(
        run_cmd.run,
        [str(_config(tmp_path)), "--lpm", "exp"],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
    assert dispatched["config"] != tmp_path / "config.yaml"
    assert not dispatched["config"].exists()


def test_cli_workflow_wrappers_translate_runtime_errors(
    tmp_path, monkeypatch, capsys
) -> None:
    config = _config(tmp_path)

    def fail_single(*_args, **_kwargs):
        raise RuntimeError("single failure")

    def fail_temporal(*_args, **_kwargs):
        raise RuntimeError("temporal failure")

    monkeypatch.setattr(single_date_workflow, "run_single_date", fail_single)
    with pytest.raises(SystemExit) as single_exit:
        run_cmd._run_single_date(config, inline=False, verbose=False)
    assert single_exit.value.code == 1

    monkeypatch.setattr(temporal_workflow, "run_temporal", fail_temporal)
    with pytest.raises(SystemExit) as temporal_exit:
        run_cmd._run_transient(config, verbose=False)
    assert temporal_exit.value.code == 1

    output = capsys.readouterr().out
    assert "Error running workflow: single failure" in output
    assert "Error running transient workflow: temporal failure" in output


@pytest.mark.parametrize(
    ("mode_args", "workflow_module", "workflow_name", "error_heading"),
    [
        ([], single_date_workflow, "run_single_date", "Error running workflow"),
        (
            ["--transient"],
            temporal_workflow,
            "run_temporal",
            "Error running transient workflow",
        ),
    ],
)
def test_cli_run_prints_preserved_evidence_note_once_without_verbose(
    tmp_path,
    monkeypatch,
    mode_args,
    workflow_module,
    workflow_name,
    error_heading,
) -> None:
    evidence = tmp_path / "preserved-results"
    note = f"Preserved result evidence: {evidence}"

    def fail(*_args, **_kwargs):
        error = RuntimeError("convergence gate rejected the chains")
        error.add_note(note)
        raise error

    monkeypatch.setattr(workflow_module, workflow_name, fail)

    result = CliRunner().invoke(run_cmd.run, [str(_config(tmp_path)), *mode_args])

    assert result.exit_code == 1
    assert f"{error_heading}: convergence gate rejected the chains" in result.output
    assert result.output.count(note) == 1


def test_cli_run_reports_returned_result_paths(tmp_path, monkeypatch) -> None:
    config = _config(tmp_path)
    single_output = tmp_path / "single-results"
    temporal_output = tmp_path / "temporal-results"
    monkeypatch.setattr(
        single_date_workflow,
        "run_single_date",
        lambda *_args, **_kwargs: single_output,
    )
    monkeypatch.setattr(
        temporal_workflow,
        "run_temporal",
        lambda *_args, **_kwargs: temporal_output,
    )

    runner = CliRunner()
    single = runner.invoke(run_cmd.run, [str(config)])
    temporal = runner.invoke(run_cmd.run, ["--transient", str(config)])

    assert single.exit_code == 0
    assert f"Results written to: {single_output}" in single.output
    assert temporal.exit_code == 0
    assert f"Results written to: {temporal_output}" in temporal.output


def test_apply_overrides_returns_original_path_when_nothing_changes(tmp_path) -> None:
    config = _config(tmp_path)

    result = run_cmd._apply_overrides(
        config,
        transient=False,
        lpm=None,
        mh_nsteps=None,
        data_name=None,
        data_dir=None,
        data_file=None,
        verbose=False,
    )

    assert result is config
