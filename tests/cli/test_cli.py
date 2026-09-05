# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""CLI smoke tests (argument parsing + dispatch)."""

import importlib
from pathlib import Path

import click
import pytest
import yaml
from click.testing import CliRunner

import pyages.cli.commands.check as check_cmd
import pyages.cli.commands.run as run_cmd
from pyages.cli.commands.new import new_group


def _write_minimal_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "workflow:\n  kind: single_date\ndataset: {}\n",
        encoding="utf-8",
    )
    return config_path


def test_cli_help():
    runner = CliRunner()
    cli_main = importlib.import_module("pyages.cli.main")
    result = runner.invoke(cli_main.cli, ["--help"])
    assert result.exit_code == 0
    assert "PyAges" in result.output


def test_cli_check_help():
    runner = CliRunner()
    result = runner.invoke(check_cmd.check, ["--help"])
    assert result.exit_code == 0
    assert "Check PyAges" in result.output


def test_cli_check_enforces_supported_python_range():
    assert check_cmd._python_version_supported((3, 12, 0))
    assert check_cmd._python_version_supported((3, 14, 9))
    assert not check_cmd._python_version_supported((3, 11, 9))
    assert not check_cmd._python_version_supported((3, 15, 0))


def test_cli_check_validates_all_active_metadata_requirements(monkeypatch):
    declared = [
        "numpy>=2,<3",
        "pydantic>=2.9,<3",
        "packaging>=24,<27",
        'pytest>=9; extra == "dev"',
    ]
    installed = {
        "numpy": "2.5.2",
        "pydantic": "2.13.4",
        "packaging": "26.3",
    }
    monkeypatch.setattr(check_cmd.metadata, "requires", lambda _name: declared)
    monkeypatch.setattr(
        check_cmd.metadata,
        "version",
        lambda name: installed[name],
    )

    result = check_cmd._check_dependencies(verbose=False)

    assert result == check_cmd.CheckResult(passed=3, failed=0)


def test_cli_check_rejects_out_of_range_dependency(monkeypatch):
    monkeypatch.setattr(
        check_cmd.metadata,
        "requires",
        lambda _name: ["numpy>=2,<3"],
    )
    monkeypatch.setattr(check_cmd.metadata, "version", lambda _name: "1.26.4")

    result = check_cmd._check_dependencies(verbose=False)

    assert result == check_cmd.CheckResult(failed=1)


def test_cli_run_dispatch_single_date(tmp_path, monkeypatch):
    config_path = _write_minimal_config(tmp_path)
    called = {}

    def _fake_run_workflow(workflow, config, *, inline, verbose):
        called["workflow"] = workflow
        called["config"] = config
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        called["inline"] = inline
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_workflow", _fake_run_workflow)

    runner = CliRunner()
    result = runner.invoke(
        run_cmd.run,
        [
            str(config_path),
            "--inline",
            "--verbose",
            "--lpm",
            "exp_shifted",
            "--mh-nsteps",
            "1234",
            "--data-name",
            "custom.txt",
            "--data-dir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    assert called["config"] != config_path
    assert called["workflow"] == "single_date"
    assert Path(called["config"]).parent == tmp_path
    assert not Path(called["config"]).exists()
    assert called["inline"] is True
    assert called["verbose"] is True
    payload = called["payload"]
    assert payload["dataset"]["name"] == "custom.txt"
    assert payload["dataset"]["data_dir"] == str(tmp_path)
    assert payload["lpm"]["model_name"] == "exp_shifted"
    assert payload["calibration_metropolis_hastings"]["nstep"] == 1234


def test_cli_run_dispatch_temporal(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "workflow:\n  kind: temporal\ndataset:\n  file: data.txt\n",
        encoding="utf-8",
    )
    called = {}

    def _fake_run_workflow(workflow, config, *, inline, verbose):
        called["workflow"] = workflow
        called["config"] = config
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_workflow", _fake_run_workflow)

    runner = CliRunner()
    result = runner.invoke(
        run_cmd.run,
        [
            str(config_path),
            "--lpm",
            "ig",
            "--mh-nsteps",
            "987",
            "--data-file",
            str(tmp_path / "data.txt"),
        ],
    )
    assert result.exit_code == 0
    assert called["config"] != config_path
    assert called["workflow"] == "temporal"
    assert Path(called["config"]).parent == tmp_path
    assert not Path(called["config"]).exists()
    assert called["verbose"] is False
    payload = called["payload"]
    assert payload["dataset"]["file"] == str(tmp_path / "data.txt")
    assert payload["lpm_models"]["list"] == ["ig"]
    assert payload["calibration"]["mh_nsteps"] == 987


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"workflow": {"kind": "single_date"}}, "single_date"),
        ({"workflow": {"kind": "temporal"}}, "temporal"),
    ],
)
def test_cli_detects_declared_workflows(payload, expected) -> None:
    assert run_cmd._detect_workflow(payload) == expected


@pytest.mark.parametrize("payload", [{}, {"dataset": {}}, {"workflow": {}}])
def test_cli_rejects_missing_workflow_kind(payload) -> None:
    with pytest.raises(click.ClickException, match="workflow.kind is required"):
        run_cmd._detect_workflow(payload)


def test_cli_new_lpm_writes_to_current_project() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(new_group, ["lpm", "audit_model"])

        assert result.exit_code == 0, result.output
        model_path = Path("pyages/lpm/models/audit_model.py")
        assert model_path.is_file()
        assert Path("data_core/data_lpm/audit_model/params.yaml").is_file()
        model_source = model_path.read_text(encoding="utf-8")
        assert "class AuditModelLpm" in model_source
        assert "def cdf_and_partial_first_moment" in model_source
        compile(model_source, str(model_path), "exec")


def test_cli_new_lpm_rejects_removed_scipy_safe_base() -> None:
    result = CliRunner().invoke(
        new_group,
        ["lpm", "audit_model", "--base", "scipy_safe"],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--base'" in result.output


def test_cli_new_tracer_writes_to_current_project() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(new_group, ["tracer", "audit_tracer"])

        assert result.exit_code == 0, result.output
        assert Path("data_core/data_tracer/audit_tracer/audit_tracer.yaml").is_file()
        assert Path("data_core/data_tracer/audit_tracer/recharge.csv").is_file()
