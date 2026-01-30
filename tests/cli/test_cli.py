# -*- coding: utf-8 -*-
"""CLI smoke tests (argument parsing + dispatch)."""

from pathlib import Path

from click.testing import CliRunner

import importlib
import pyage.cli.commands.run as run_cmd
import pyage.cli.commands.check as check_cmd


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
        called["inline"] = inline
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_single_date", _fake_run_single_date)

    runner = CliRunner()
    result = runner.invoke(run_cmd.run, [str(config_path), "--inline", "--verbose"])
    assert result.exit_code == 0
    assert called["config"] == config_path
    assert called["inline"] is True
    assert called["verbose"] is True


def test_cli_run_dispatch_transient(tmp_path, monkeypatch):
    config_path = _write_minimal_config(tmp_path)
    called = {}

    def _fake_run_transient(config, verbose):
        called["config"] = config
        called["verbose"] = verbose

    monkeypatch.setattr(run_cmd, "_run_transient", _fake_run_transient)

    runner = CliRunner()
    result = runner.invoke(run_cmd.run, [str(config_path), "--transient"])
    assert result.exit_code == 0
    assert called["config"] == config_path
    assert called["verbose"] is False
