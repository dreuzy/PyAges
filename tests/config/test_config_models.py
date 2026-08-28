# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Strict contracts for user-facing YAML configuration models."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from pyages.config.models import (
    LauncherConfig,
    LauncherDatasetCfg,
    LauncherLpmCfg,
    LauncherMetropolisCfg,
    LauncherObjectiveCfg,
    LauncherReachableCfg,
    LauncherRunCfg,
    LauncherSimplexCfg,
    TemporalCalibrationCfg,
    TemporalDatasetCfg,
    TemporalFiguresCfg,
    TemporalLpmModelsCfg,
    TemporalParams,
    TemporalResultsCfg,
)
from pyages.lpm import list_available_lpms

ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION_DOC = ROOT / "docs" / "user-guide" / "configuration.md"


def _yaml_after_heading(document: str, heading: str) -> dict:
    section = document.split(heading, maxsplit=1)[1]
    match = re.search(r"```yaml\s*\n(.*?)```", section, flags=re.DOTALL)
    assert match is not None, f"No YAML example found after {heading}"
    payload = yaml.safe_load(match.group(1))
    assert isinstance(payload, dict)
    return payload


def _defaults_after_heading(document: str, heading: str) -> dict:
    section = document.split(heading, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|")
    ]
    header = next(row for row in rows if row and row[0] == "Field")
    default_index = header.index("Default")
    defaults = {}
    for row in rows[2:]:
        if len(row) <= default_index:
            continue
        field = row[0].strip("`")
        raw = row[default_index].strip("`")
        defaults[field] = yaml.safe_load(raw)
    return defaults


def _model_defaults(model) -> dict:
    return {name: field.default for name, field in model.model_fields.items()}


def _required_after_heading(document: str, heading: str) -> dict[str, bool]:
    section = document.split(heading, maxsplit=1)[1].split("\n### ", maxsplit=1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|")
    ]
    header = next(row for row in rows if row and row[0] == "Field")
    required_index = header.index("Required")
    required = {}
    for row in rows[2:]:
        if len(row) <= required_index:
            continue
        field = row[0].strip("`")
        required[field] = row[required_index].casefold() == "yes"
    return required


def _model_required(model) -> dict[str, bool]:
    return {name: field.is_required() for name, field in model.model_fields.items()}


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/templates/quickstart_single.yaml",
        "examples/natural/albuquerque/exemple_albuquerque.yaml",
        "examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml",
        "examples/natural/ploemeur/exemple_ploemeur.yaml",
        "examples/synthetic/lpm_recovery_single_date/lpm_recovery_single_date.yaml",
    ],
)
def test_shipped_single_date_configs_are_strictly_valid(relative_path):
    path = ROOT / relative_path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    LauncherConfig.model_validate(payload, context={"root_dir": ROOT})


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/templates/quickstart_temporal.yaml",
        "examples/natural/ploemeur_temporal/ploemeur_temporal.yaml",
    ],
)
def test_shipped_temporal_configs_are_strictly_valid(relative_path):
    path = ROOT / relative_path
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    TemporalParams.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (LauncherConfig, {"dataset": {}, "obsolete_option": True}),
        (
            LauncherConfig,
            {"dataset": {"name": "sample.txt", "obsolete_option": True}},
        ),
        (
            TemporalParams,
            {"dataset": {"file": "sample.txt"}, "obsolete_option": True},
        ),
        (
            TemporalParams,
            {"dataset": {"file": "sample.txt", "obsolete_option": True}},
        ),
    ],
)
def test_unknown_configuration_keys_are_rejected(model, payload):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(payload)


def test_documented_single_date_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    headings = (
        "### Dataset Section",
        "### LPM Section",
        "### Tracer Data Override",
        "### Run Section",
        "### Reachable Concentrations Section",
        "### Objective Function Section",
        "### Metropolis-Hastings Section",
        "### Simplex Section",
    )
    payload = {}
    for heading in headings:
        payload.update(_yaml_after_heading(document, heading))

    LauncherConfig.model_validate(payload, context={"root_dir": ROOT})


def test_documented_temporal_yaml_sections_form_a_valid_configuration():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    temporal = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]
    headings = (
        "### Dataset Section",
        "### LPM Models Section",
        "### Workflow Section",
        "### Calibration Section",
        "### Figures Section",
        "### Results Section",
    )
    payload = {}
    for heading in headings:
        payload.update(_yaml_after_heading(temporal, heading))

    TemporalParams.model_validate(payload)


def test_documented_lpm_table_matches_runtime_registry():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    table = document.split("**Available LPM models:**", maxsplit=1)[1].split(
        "The model-specific meaning", maxsplit=1
    )[0]
    documented = set(re.findall(r"^\| `([^`]+)` \|", table, flags=re.MULTILINE))

    assert documented == set(list_available_lpms())


@pytest.mark.parametrize(
    ("heading", "model", "temporal_only"),
    [
        ("### Reachable Concentrations Section", LauncherReachableCfg, False),
        ("### Objective Function Section", LauncherObjectiveCfg, False),
        ("### Metropolis-Hastings Section", LauncherMetropolisCfg, False),
        ("### Simplex Section", LauncherSimplexCfg, False),
        ("### Calibration Section", TemporalCalibrationCfg, True),
        ("### Figures Section", TemporalFiguresCfg, True),
        ("### Results Section", TemporalResultsCfg, True),
    ],
)
def test_documented_default_tables_match_pydantic_models(heading, model, temporal_only):
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    if temporal_only:
        document = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]

    assert _defaults_after_heading(document, heading) == _model_defaults(model)


@pytest.mark.parametrize(
    ("heading", "model", "temporal_only"),
    [
        ("### Dataset Section", LauncherDatasetCfg, False),
        ("### LPM Section", LauncherLpmCfg, False),
        ("### Dataset Section", TemporalDatasetCfg, True),
        ("### LPM Models Section", TemporalLpmModelsCfg, True),
    ],
)
def test_documented_required_fields_match_pydantic_models(
    heading, model, temporal_only
):
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    if temporal_only:
        document = document.split("## Temporal Workflow Configuration", maxsplit=1)[1]

    assert _required_after_heading(document, heading) == _model_required(model)


def test_documented_single_date_run_defaults_remain_all_enabled():
    defaults = _model_defaults(LauncherRunCfg)

    assert defaults
    assert all(value is True for value in defaults.values())


def test_single_date_mh_requires_at_least_one_retained_state() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 11"):
        LauncherMetropolisCfg(nstep=10)

    assert LauncherMetropolisCfg(nstep=11).nstep == 11


def test_temporal_fixed_seed_requires_a_non_negative_value() -> None:
    with pytest.raises(ValidationError, match="seed is required"):
        TemporalCalibrationCfg(seed_enabled=True)
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        TemporalCalibrationCfg(seed_enabled=True, seed=-1)

    assert TemporalCalibrationCfg(seed_enabled=True, seed=0).seed == 0


def test_temporal_relative_error_must_be_strictly_positive() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDatasetCfg(file="observations.txt", error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        TemporalDatasetCfg(file="observations.txt", missing_error_rel=0.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        LauncherDatasetCfg(missing_error_rel=0.0)


@pytest.mark.parametrize("models", [[], ["exp", ""], ["exp", "exp"]])
def test_temporal_explicit_model_list_must_be_unambiguous(models) -> None:
    with pytest.raises(ValidationError, match="lpm_models.list"):
        TemporalLpmModelsCfg(list=models)


def test_all_documented_yaml_blocks_are_parseable():
    document = CONFIGURATION_DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```yaml\s*\n(.*?)```", document, flags=re.DOTALL)

    assert blocks
    for block in blocks:
        yaml.safe_load(block)
