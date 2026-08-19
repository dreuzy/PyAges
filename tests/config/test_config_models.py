"""Strict contracts for user-facing YAML configuration models."""

from pathlib import Path

from pydantic import ValidationError
import pytest
import yaml

from pyage.config.models import LauncherConfig, TemporalParams


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "relative_path",
    [
        "examples/templates/quickstart_single.yaml",
        "examples/natural/albuquerque/exemple_albuquerque.yaml",
        "examples/natural/albuquerque/exemple_albuquerque_shapefree.yaml",
        "examples/natural/fontainebleau/exemple_fontainebleau.yaml",
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
