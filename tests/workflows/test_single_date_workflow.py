# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Characterization tests for the installed single-date workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date

ROOT = Path(__file__).resolve().parents[2]


def test_quickstart_writes_a_manifest_and_normalized_observations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "quickstart"
    monkeypatch.setattr(
        single_context, "dataset_results_directory", lambda _name: output
    )
    monkeypatch.setattr(
        single_reporting,
        "export_concentration_chronicles",
        lambda *_args, **_kwargs: None,
    )

    result = single_date.run_single_date(
        Path("examples/templates/quickstart_single.yaml"),
        force_inline=True,
    )

    assert result == output
    assert (output / "concentrations.txt").is_file()
    observations = pd.read_table(output / "concentrations.txt")
    assert observations.columns.tolist() == [
        "element",
        "concentration",
        "error",
        "unit",
        "date",
    ]
    assert (observations["error"] > 0.0).all()
    manifest = json.loads((output / "result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["workflow"] == "single_date"
    assert manifest["status"] == "complete"
    assert manifest["configuration"]["path"].endswith("quickstart_single.yaml")
    assert "concentrations.txt" in manifest["artifacts_sha256"]
    assert manifest["details"]["dataset_year"] == 2010
    assert manifest["details"]["observation_error_policy"]["missing_error_rel"] == 0.01
    assert manifest["details"]["observation_error_policy"]["transformations"]
    assert any(item["path"].endswith("params.yaml") for item in manifest["inputs"])


def test_quickstart_exercised_here_is_the_documented_tutorial_command() -> None:
    tutorial = (ROOT / "docs" / "user-guide" / "tutorial.md").read_text(
        encoding="utf-8"
    )

    assert "pyages run examples/templates/quickstart_single.yaml" in tutorial
    assert '`"status": "complete"`' not in tutorial
    assert '"status": "complete"' in tutorial


def test_objective_only_run_uses_resolved_errors_without_calibration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_config = ROOT / "examples" / "templates" / "quickstart_single.yaml"
    payload = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    payload["dataset"]["data_dir"] = str(
        ROOT / "examples" / "natural" / "ploemeur" / "data"
    )
    payload["lpm"]["data_directory"] = str(ROOT / "data_core" / "data_lpm")
    payload["run"]["objective_function"] = True
    payload["objective_function"]["nmodels"] = 4
    config = tmp_path / "objective_only.yaml"
    config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    output = tmp_path / "objective_only"
    monkeypatch.setattr(
        single_context, "dataset_results_directory", lambda _name: output
    )
    monkeypatch.setattr(
        single_reporting,
        "export_concentration_chronicles",
        lambda *_args, **_kwargs: None,
    )

    result = single_date.run_single_date(config, force_inline=True)

    assert result == output
    assert (output / "objective_function_grid.txt").is_file()
    observations = pd.read_table(output / "concentrations.txt")
    assert (observations["error"] > 0.0).all()
