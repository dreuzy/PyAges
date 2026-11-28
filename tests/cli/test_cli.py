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
        "schema_version: 3\nworkflow:\n  kind: single_date\ndata: {}\n",
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


def test_cli_check_lpm_runs_fast_integration_contract() -> None:
    result = CliRunner().invoke(check_cmd.check, ["lpm", "exp"])

    assert result.exit_code == 0, result.output
    assert "constant-and-affine-convolution" in result.output
    assert "satisfies the PyAges integration contract" in result.output


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
    assert payload["data"]["name"] == "custom.txt"
    assert payload["data"]["data_dir"] == str(tmp_path)
    assert payload["lpm"]["models"] == ["exp_shifted"]
    assert payload["calibration"]["metropolis_hastings"]["nsteps"] == 1234


def test_cli_run_dispatch_temporal(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "schema_version: 3\nworkflow:\n  kind: temporal\ndata:\n  file: data.txt\n",
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
    assert payload["data"]["file"] == str(tmp_path / "data.txt")
    assert payload["lpm"]["models"] == ["ig"]
    assert payload["calibration"]["metropolis_hastings"]["nsteps"] == 987


def test_cli_enables_and_overrides_deterministic_objective(tmp_path, monkeypatch):
    config_path = _write_minimal_config(tmp_path)
    called = {}

    def _fake_run_workflow(workflow, config, *, inline, verbose):
        called["workflow"] = workflow
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))

    monkeypatch.setattr(run_cmd, "_run_workflow", _fake_run_workflow)

    result = CliRunner().invoke(
        run_cmd.run,
        [
            str(config_path),
            "--deterministic-inversion",
            "--objective-loss",
            "l1",
            "--objective-scale",
            "relative",
        ],
    )

    assert result.exit_code == 0, result.output
    assert called["workflow"] == "single_date"
    assert called["payload"]["run"]["deterministic_inversion"] is True
    objective = called["payload"]["calibration"]["deterministic_inversion"]
    assert objective == {"loss": "l1", "scale": "relative"}


def test_cli_warns_and_ignores_deterministic_objective_for_temporal(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "temporal.yaml"
    config_path.write_text(
        "schema_version: 3\nworkflow:\n  kind: temporal\ndata:\n  file: data.txt\n",
        encoding="utf-8",
    )

    called = {}

    def _fake_run_workflow(workflow, config, *, inline, verbose):
        called["payload"] = yaml.safe_load(Path(config).read_text(encoding="utf-8"))

    monkeypatch.setattr(run_cmd, "_run_workflow", _fake_run_workflow)
    result = CliRunner().invoke(
        run_cmd.run,
        [str(config_path), "--objective-loss", "l1"],
    )

    assert result.exit_code == 0, result.output
    assert "Ignoring deterministic objective options" in result.output
    assert "deterministic_inversion" not in called["payload"].get("run", {})


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"schema_version": 3, "workflow": {"kind": "single_date"}}, "single_date"),
        ({"schema_version": 3, "workflow": {"kind": "temporal"}}, "temporal"),
    ],
)
def test_cli_detects_declared_workflows(payload, expected) -> None:
    assert run_cmd._detect_workflow(payload) == expected


@pytest.mark.parametrize("payload", [{"schema_version": 3, "workflow": {}}])
def test_cli_rejects_missing_workflow_kind(payload) -> None:
    with pytest.raises(click.ClickException, match="workflow.kind is required"):
        run_cmd._detect_workflow(payload)


@pytest.mark.parametrize("payload", [{}, {"schema_version": 2}])
def test_cli_rejects_non_schema_3_configurations(payload) -> None:
    with pytest.raises(click.ClickException, match="schema_version"):
        run_cmd._detect_workflow(payload)


def test_cli_transient_option_has_been_removed(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        run_cmd.run, [str(_write_minimal_config(tmp_path)), "--transient"]
    )

    assert result.exit_code == 2
    assert "No such option" in result.output
    assert "--transient" in result.output


def test_schema_3_cli_overrides_use_canonical_fields(tmp_path) -> None:
    payload = {
        "schema_version": 3,
        "workflow": {"kind": "temporal"},
        "data": {"file": "old.tsv"},
    }

    changed = run_cmd._apply_overrides(
        payload,
        workflow="temporal",
        lpm="ig",
        mh_nsteps=456,
        data_name=None,
        data_dir=None,
        data_file=tmp_path / "observations.tsv",
    )

    assert changed is True
    assert payload["data"]["file"] == str(tmp_path / "observations.tsv")
    assert payload["lpm"]["models"] == ["ig"]
    assert payload["calibration"]["metropolis_hastings"]["nsteps"] == 456


def test_cli_new_lpm_writes_to_current_project(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(new_group, ["lpm", "audit_model"])

    assert result.exit_code == 0, result.output
    model_path = Path("pyages/lpm/models/audit_model.py")
    assert model_path.is_file()
    assert Path("data_core/data_lpm/audit_model/params.yaml").is_file()
    model_source = model_path.read_text(encoding="utf-8")
    params_source = Path("data_core/data_lpm/audit_model/params.yaml").read_text(
        encoding="utf-8"
    )
    assert "Generated by the PyAges LPM template generator" in model_source
    assert "This is a complete working starter" in model_source
    assert '"""Translate mean and shape to SciPy' in model_source
    assert "class AuditModelLpm" in model_source
    assert "def cdf_and_partial_first_moment" in model_source
    assert "Generated by ``pyages new lpm audit_model``" in params_source
    compile(model_source, str(model_path), "exec")


def test_cli_new_lpm_rejects_removed_scipy_safe_base() -> None:
    result = CliRunner().invoke(
        new_group,
        ["lpm", "audit_model", "--base", "scipy_safe"],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--base'" in result.output


def test_cli_new_lpm_plugin_writes_complete_root_project(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        new_group,
        ["lpm", "audit_power", "--layout", "plugin", "--base", "root"],
    )

    assert result.exit_code == 0, result.output
    project = Path("pyages-lpm-audit-power")
    assert (project / "pyproject.toml").is_file()
    model = project / "src/pyages_lpm_audit_power/model.py"
    params = project / "src/pyages_lpm_audit_power/data_lpm/audit_power/params.yaml"
    assert model.is_file()
    assert params.is_file()
    source = model.read_text(encoding="utf-8")
    init_source = (project / "src/pyages_lpm_audit_power/__init__.py").read_text(
        encoding="utf-8"
    )
    test_source = (project / "tests/test_model.py").read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert "class AuditPowerLpm(LpmBase)" in source
    assert "definition = LpmDefinition(" in source
    assert "This complete law demonstrates every method" in source
    assert '"""Return the exact full first moment' in source
    assert "from scipy" not in source
    assert "Generated by the PyAges LPM template generator" in init_source
    assert (
        "Exercise installed discovery and basic probability invariants" in test_source
    )
    assert "## Start here" in readme
    assert "## Read parameter limits" in readme
    assert "`min_inclusive: false` means `value > min`" in readme
    assert "scientific validation" in readme
    assert "Plugin LPM" not in readme
    assert "Installing the distribution records" in pyproject
    compile(source, str(model), "exec")
    compile(init_source, "generated-plugin:__init__", "exec")
    compile(test_source, "generated-plugin:test_model", "exec")


def test_cli_new_lpm_plugin_writes_scipy_adapter(tmp_path, monkeypatch) -> None:
    """Keep the SciPy plugin variant paired with its dependency and formulas."""
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        new_group,
        ["lpm", "audit_gamma", "--layout", "plugin", "--base", "scipy"],
    )

    assert result.exit_code == 0, result.output
    project = Path("pyages-lpm-audit-gamma")
    model = project / "src/pyages_lpm_audit_gamma/model.py"
    source = model.read_text(encoding="utf-8")
    pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "class AuditGammaLpm(LpmScipy)" in source
    assert "scipy_dist = gamma" in source
    assert '"scipy>=1.14,<1.19"' in pyproject
    assert "SciPy supplies the standard probability functions" in readme
    compile(source, str(model), "exec")


def test_cli_new_tracer_writes_to_current_project(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(new_group, ["tracer", "audit_tracer"])

    assert result.exit_code == 0, result.output
    assert Path("data_core/data_tracer/audit_tracer/audit_tracer.yaml").is_file()
    assert Path("data_core/data_tracer/audit_tracer/recharge.csv").is_file()
