# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Installed CLI contracts for quickstart creation and config migration."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from pyages.cli.main import cli
from pyages.config.loading import resolve_from
from pyages.config.migration import (
    configuration_base_directory,
    normalize_configuration_payload,
)
from pyages.config.models import LauncherConfig, TemporalParams


def test_new_config_creates_installed_single_date_quickstart(tmp_path: Path) -> None:
    destination = tmp_path / "quickstart"

    result = CliRunner().invoke(cli, ["new", "config", str(destination)])

    assert result.exit_code == 0, result.output
    config_path = destination / "pyages.yaml"
    data_path = destination / "data" / "observations.tsv"
    assert config_path.is_file()
    assert data_path.is_file()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    runtime = normalize_configuration_payload(payload)
    config = LauncherConfig.model_validate(
        runtime,
        context={"root_dir": destination},
    )
    assert payload["schema_version"] == 2
    assert config.dataset.data_dir == destination / "data"
    assert "pyages run" in result.output


def test_new_config_creates_temporal_quickstart_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "temporal"
    runner = CliRunner()

    created = runner.invoke(
        cli,
        ["new", "config", str(destination), "--kind", "temporal"],
    )
    repeated = runner.invoke(
        cli,
        ["new", "config", str(destination), "--kind", "temporal"],
    )

    assert created.exit_code == 0, created.output
    assert repeated.exit_code == 1
    assert "already exist" in repeated.output
    payload = yaml.safe_load((destination / "pyages.yaml").read_text(encoding="utf-8"))
    config = TemporalParams.model_validate(normalize_configuration_payload(payload))
    assert config.workflow.kind == "temporal"
    assert config.dataset.file == "data/observations.tsv"


def test_config_migrate_writes_schema_2_beside_untouched_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.yaml"
    destination = tmp_path / "canonical.yaml"
    source_text = """# retained only in source
workflow:
  kind: single_date
dataset:
  name: observations.tsv
lpm:
  model_name: exp
calibration_metropolis_hastings:
  nstep: 500
  nskip: 5
"""
    source.write_text(source_text, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["config", "migrate", str(source), str(destination)],
    )

    assert result.exit_code == 0, result.output
    assert source.read_text(encoding="utf-8") == source_text
    canonical = yaml.safe_load(destination.read_text(encoding="utf-8"))
    legacy_base = configuration_base_directory(
        source,
        yaml.safe_load(source_text),
    )
    assert canonical["schema_version"] == 2
    assert canonical["lpm"]["models"] == ["exp"]
    assert (
        resolve_from(destination.parent, canonical["data"]["data_dir"])
        == (legacy_base / "examples" / "data").resolve()
    )
    assert (
        resolve_from(destination.parent, canonical["lpm"]["directory"])
        == (legacy_base / "data_core" / "data_lpm").resolve()
    )
    assert canonical["calibration"]["metropolis_hastings"]["nsteps"] == 500
    assert "comments are not preserved" in result.output


def test_config_migrate_rebases_nested_single_date_paths(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    case_directory = checkout / "examples" / "case"
    case_directory.mkdir(parents=True)
    (checkout / "data_core").mkdir()
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    source = case_directory / "legacy.yaml"
    destination = case_directory / "canonical.yaml"
    source.write_text(
        """workflow:
  kind: single_date
dataset:
  name: observations.tsv
  data_dir: inputs
lpm:
  model_name: exp
  data_directory: models
tracers:
  data_directory: tracer-data
results:
  use_default: false
  directory: outputs
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["config", "migrate", str(source), str(destination)],
    )

    assert result.exit_code == 0, result.output
    canonical = yaml.safe_load(destination.read_text(encoding="utf-8"))
    runtime = normalize_configuration_payload(canonical)
    config = LauncherConfig.model_validate(
        runtime,
        context={"root_dir": destination.parent},
    )
    assert config.dataset.data_dir.resolve() == (checkout / "inputs").resolve()
    assert config.lpm.data_directory.resolve() == (checkout / "models").resolve()
    assert config.tracers.data_directory is not None
    assert (
        config.tracers.data_directory.resolve() == (checkout / "tracer-data").resolve()
    )
    assert config.results.directory is not None
    assert config.results.directory.resolve() == (checkout / "outputs").resolve()


def test_config_migrate_rebases_nested_temporal_paths(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    case_directory = checkout / "examples" / "temporal"
    case_directory.mkdir(parents=True)
    (checkout / "data_core").mkdir()
    (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    source = case_directory / "legacy.yaml"
    destination = case_directory / "canonical.yaml"
    source.write_text(
        """workflow:
  kind: temporal
dataset:
  file: inputs/observations.tsv
lpm_models:
  models: [exp]
  directory: models
results:
  use_default: false
  directory: outputs
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli,
        ["config", "migrate", str(source), str(destination)],
    )

    assert result.exit_code == 0, result.output
    canonical = yaml.safe_load(destination.read_text(encoding="utf-8"))
    config = TemporalParams.model_validate(normalize_configuration_payload(canonical))
    assert (
        resolve_from(destination.parent, config.dataset.file)
        == (checkout / "inputs" / "observations.tsv").resolve()
    )
    assert config.lpm_models.directory is not None
    assert (
        resolve_from(destination.parent, config.lpm_models.directory)
        == (checkout / "models").resolve()
    )
    assert config.results.directory is not None
    assert (
        resolve_from(destination.parent, config.results.directory)
        == (checkout / "outputs").resolve()
    )


def test_config_migrate_refuses_relocation_and_existing_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.yaml"
    source.write_text("workflow:\n  kind: single_date\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    existing = tmp_path / "existing.yaml"
    existing.write_text("do not replace", encoding="utf-8")
    runner = CliRunner()

    relocated = runner.invoke(
        cli,
        ["config", "migrate", str(source), str(elsewhere / "new.yaml")],
    )
    overwritten = runner.invoke(
        cli,
        ["config", "migrate", str(source), str(existing)],
    )

    assert relocated.exit_code == 1
    assert "must be beside" in relocated.output
    assert overwritten.exit_code == 1
    assert "already exists" in overwritten.output
    assert existing.read_text(encoding="utf-8") == "do not replace"
