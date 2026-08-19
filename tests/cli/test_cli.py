# -*- coding: utf-8 -*-
"""CLI smoke tests (argument parsing + dispatch)."""

import importlib
from pathlib import Path

import yaml
from click.testing import CliRunner

import pyage.cli.commands.check as check_cmd
import pyage.cli.commands.run as run_cmd
from pyage.cli.commands.new import new_group


def _write_minimal_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("dataset: {}\n", encoding="utf-8")
    return config_path


def test_cli_help():
    runner = CliRunner()
    cli_main = importlib.import_module("pyage.cli.main")
    result = runner.invoke(cli_main.cli, ["--help"])
    assert result.exit_code == 0
    assert "PyAge" in result.output


def test_cli_check_help():
    runner = CliRunner()
    result = runner.invoke(check_cmd.check, ["--help"])
    assert result.exit_code == 0
    assert "Check PyAge" in result.output


def test_cli_run_dispatch_single_date(tmp_path, monkeypatch):
    config_path = _write_minimal_config(tmp_path)
    called = {}

    def _fake_run_single_date(config, inline, verbose):
        called["config"] = config
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        called["inline"] = inline
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_single_date", _fake_run_single_date)

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
    assert Path(called["config"]).parent == tmp_path
    assert not Path(called["config"]).exists()
    assert called["inline"] is True
    assert called["verbose"] is True
    payload = called["payload"]
    assert payload["dataset"]["name"] == "custom.txt"
    assert payload["dataset"]["data_dir"] == str(tmp_path)
    assert payload["lpm"]["model_name"] == "exp_shifted"
    assert payload["calibration_metropolis_hastings"]["nstep"] == 1234


def test_cli_run_dispatch_transient(tmp_path, monkeypatch):
    config_path = _write_minimal_config(tmp_path)
    called = {}

    def _fake_run_transient(config, verbose):
        called["config"] = config
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_transient", _fake_run_transient)

    runner = CliRunner()
    result = runner.invoke(
        run_cmd.run,
        [
            str(config_path),
            "--transient",
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
    assert Path(called["config"]).parent == tmp_path
    assert not Path(called["config"]).exists()
    assert called["verbose"] is False
    payload = called["payload"]
    assert payload["dataset"]["file"] == str(tmp_path / "data.txt")
    assert payload["lpm_models"]["list"] == ["ig"]
    assert payload["calibration"]["mh_nsteps"] == 987


def test_cli_new_lpm_writes_to_current_project() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(new_group, ["lpm", "audit_model"])

        assert result.exit_code == 0, result.output
        assert Path("pyage/lpm/models/LPM_audit_model.py").is_file()
        assert Path("data_core/data_lpm/audit_model/params.yaml").is_file()


def test_cli_new_tracer_writes_to_current_project() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(new_group, ["tracer", "audit_tracer"])

        assert result.exit_code == 0, result.output
        assert Path("data_core/data_tracer/audit_tracer/audit_tracer.yaml").is_file()
        assert Path("data_core/data_tracer/audit_tracer/recharge.csv").is_file()
