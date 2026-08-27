# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Strict configuration tests for the Ploemeur workflows."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sites.ploemeur.config.models import (
    PloemeurWorkflowConfig,
    PriorPipelinePresets,
)
from sites.ploemeur.workflows.ploemeur_workflow import (
    load_workflow_params,
    validate_workflow_params,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "sites" / "ploemeur"


def _workflow_paths() -> list[Path]:
    paths = [
        SITE_ROOT / "params" / "ploemeur_full.yaml",
        SITE_ROOT / "params" / "ploemeur_F09.yaml",
    ]
    paths.extend(
        sorted((SITE_ROOT / "studies" / "HYP-26-0172" / "params").glob("*.yaml"))
    )
    paths.extend(
        sorted(
            (SITE_ROOT / "studies" / "HYP-26-0172" / "archive" / "params").glob(
                "*.yaml"
            )
        )
    )
    return paths


@pytest.mark.parametrize("params_path", _workflow_paths(), ids=lambda path: path.stem)
def test_shipped_workflow_config_is_strict_and_valid(params_path: Path) -> None:
    config = validate_workflow_params(load_workflow_params(params_path))
    assert config.observations.well_dates


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.update({"obsolete_option": True}),
        lambda data: data["calibration"].update({"obsolete_option": True}),
        lambda data: data["observations"].update({"obsolete_option": True}),
        lambda data: data["lpm_models"].update({"obsolete_option": True}),
        lambda data: data["results"].update({"obsolete_option": True}),
    ],
)
def test_unknown_workflow_keys_are_rejected(mutation) -> None:
    data = load_workflow_params(SITE_ROOT / "params" / "ploemeur_F09.yaml")
    mutation(data)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PloemeurWorkflowConfig.model_validate(data)


def test_unknown_prior_preset_key_is_rejected() -> None:
    path = SITE_ROOT / "params" / "prior_pipeline_presets.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    malformed = deepcopy(data)
    malformed["independent"]["obsolete_option"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PriorPipelinePresets.model_validate(malformed)


def test_multiple_hydrological_breakups_are_rejected() -> None:
    data = load_workflow_params(SITE_ROOT / "params" / "ploemeur_F09.yaml")
    data["workflows"]["breakups"] = [2012, 2018]

    with pytest.raises(ValidationError, match="at most 1 item"):
        PloemeurWorkflowConfig.model_validate(data)
