# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Installed CLI contracts for schema-3 quickstart creation."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from pyages.cli.main import cli
from pyages.config.models import SingleDateConfig, TemporalConfig
from pyages.config.paths import DIRECTORY_LPM_DATA


def test_new_config_creates_installed_single_date_quickstart(tmp_path: Path) -> None:
    destination = tmp_path / "quickstart"

    result = CliRunner().invoke(cli, ["new", "config", str(destination)])

    assert result.exit_code == 0, result.output
    config_path = destination / "pyages.yaml"
    data_path = destination / "data" / "observations.tsv"
    assert config_path.is_file()
    assert data_path.is_file()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = SingleDateConfig.model_validate(
        payload,
        context={"root_dir": destination},
    )
    assert payload["schema_version"] == 3
    assert config.data.data_dir == destination / "data"
    assert config.lpm.directory == DIRECTORY_LPM_DATA
    assert (config.lpm.directory / config.lpm.models[0] / "params.yaml").is_file()
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
    config = TemporalConfig.model_validate(payload)
    assert config.workflow.kind == "temporal"
    assert config.data.file == "data/observations.tsv"


def test_removed_configuration_command_is_absent() -> None:
    result = CliRunner().invoke(cli, ["config"])

    assert result.exit_code == 2
    assert "No such command 'config'" in result.output
