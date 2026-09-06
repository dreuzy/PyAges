# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Compatibility contracts for the PyAges 1.2 configuration boundary."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from pyages.config.migration import (
    LegacyConfigurationWarning,
    migrate_configuration_payload,
    normalize_configuration_payload,
)
from pyages.config.models import LauncherConfig, TemporalLpmModelsCfg, TemporalParams
from pyages.config.paths import DIRECTORY_LPM_DATA
from pyages.workflows.single_date.config import load_config_payload, load_params_payload


def test_schema_2_single_date_uses_common_sections(tmp_path: Path) -> None:
    payload = {
        "schema_version": 2,
        "workflow": {"kind": "single_date"},
        "data": {"name": "observations.tsv", "data_dir": "data"},
        "lpm": {"models": ["exp_shifted"]},
        "calibration": {
            "metropolis_hastings": {"nsteps": 321, "thinning": 3},
            "simplex": {"fuq_n": 7},
        },
        "output": {
            "use_default": False,
            "directory": "results",
        },
    }

    config = load_config_payload(tmp_path, payload)

    assert config.dataset.data_dir == tmp_path / "data"
    assert config.lpm.model_name == "exp_shifted"
    assert config.lpm.data_directory == DIRECTORY_LPM_DATA
    assert config.calibration_metropolis_hastings.nstep == 321
    assert config.calibration_metropolis_hastings.nskip == 3
    assert config.calibration_simplex.fuq_n == 7
    assert config.results.directory == tmp_path / "results"


def test_schema_2_temporal_uses_common_sections() -> None:
    payload = {
        "schema_version": 2,
        "workflow": {"kind": "temporal", "mode": "span"},
        "data": {"file": "data/observations.tsv"},
        "lpm": {"models": ["ig"]},
        "calibration": {
            "metropolis_hastings": {
                "nsteps": 401,
                "thinning": 4,
                "seed": 19,
            }
        },
        "reporting": {"temporal": True},
        "output": {"study_name": "audit"},
    }

    runtime = normalize_configuration_payload(payload, expected_kind="temporal")
    config = TemporalParams.model_validate(runtime)

    assert config.dataset.file == "data/observations.tsv"
    assert config.lpm_models.models == ["ig"]
    assert config.calibration.mh_nsteps == 401
    assert config.calibration.nskip == 4
    assert config.calibration.seed_enabled is True
    assert config.calibration.seed == 19
    assert config.figures.temporal is True
    assert config.results.study_name == "audit"


def test_unversioned_1x_payload_is_preserved_and_warns() -> None:
    payload = {
        "workflow": {"kind": "single_date"},
        "lpm": {"model_name": "exp"},
    }
    original = copy.deepcopy(payload)

    with pytest.warns(LegacyConfigurationWarning, match="remains supported"):
        normalized = normalize_configuration_payload(payload)

    assert normalized == original
    assert payload == original


def test_legacy_workflow_default_and_temporal_list_alias_remain_compatible() -> None:
    with pytest.warns(LegacyConfigurationWarning):
        single = normalize_configuration_payload({}, expected_kind="single_date")
    assert single["workflow"] == {"kind": "single_date"}

    temporal_payload = {
        "dataset": {"file": "observations.tsv"},
        "lpm_models": {"list": ["exp"]},
    }
    with pytest.warns(LegacyConfigurationWarning):
        temporal = normalize_configuration_payload(
            temporal_payload,
            expected_kind="temporal",
        )
    assert temporal["workflow"] == {"kind": "temporal"}
    assert temporal["lpm_models"] == {"models": ["exp"]}


def test_direct_temporal_model_keeps_deprecated_list_alias() -> None:
    with pytest.warns(DeprecationWarning, match="lpm_models.list"):
        config = TemporalLpmModelsCfg.model_validate({"list": ["exp"]})
    assert config.models == ["exp"]

    with pytest.raises(ValueError, match="cannot be combined"):
        TemporalLpmModelsCfg.model_validate({"list": ["exp"], "models": ["ig"]})


def test_flattened_single_date_view_remains_compatible(tmp_path: Path) -> None:
    with pytest.warns(DeprecationWarning) as captured:
        params = load_params_payload(
            tmp_path,
            {
                "workflow": {"kind": "single_date"},
                "dataset": {"name": "observations.tsv", "data_dir": "data"},
                "lpm": {"model_name": "exp"},
            },
        )

    warning_messages = [str(item.message) for item in captured]
    assert any("load_config_payload" in message for message in warning_messages)
    assert any("Unversioned PyAges 1.x" in message for message in warning_messages)
    assert params.dataset_name == "observations.tsv"
    assert params.dataset_data_dir == tmp_path / "data"
    assert params.lpm_model_name == "exp"


@pytest.mark.parametrize("version", [1, 3, "2", True, None])
def test_invalid_schema_versions_are_rejected(version: object) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        normalize_configuration_payload(
            {
                "schema_version": version,
                "workflow": {"kind": "single_date"},
            }
        )


def test_single_date_schema_2_requires_exactly_one_lpm() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        normalize_configuration_payload(
            {
                "schema_version": 2,
                "workflow": {"kind": "single_date"},
                "lpm": {"models": ["exp", "ig"]},
            }
        )


def test_legacy_migration_round_trips_single_date_semantics() -> None:
    legacy = {
        "workflow": {"kind": "single_date"},
        "dataset": {"name": "observations.tsv", "data_dir": "data"},
        "lpm": {"model_name": "exp", "data_directory": "models"},
        "calibration_metropolis_hastings": {
            "nstep": 500,
            "burn_in": 0.2,
            "nskip": 5,
            "seed": 12,
        },
        "calibration_simplex": {"fuq_n": 8},
        "results": {"study_name": "legacy"},
    }

    canonical = migrate_configuration_payload(legacy)
    runtime = normalize_configuration_payload(canonical)
    config = LauncherConfig.model_validate(runtime)

    assert canonical["schema_version"] == 2
    assert canonical["lpm"]["models"] == ["exp"]
    assert canonical["calibration"]["metropolis_hastings"]["nsteps"] == 500
    assert canonical["calibration"]["metropolis_hastings"]["thinning"] == 5
    assert config.lpm.model_name == "exp"
    assert config.calibration_metropolis_hastings.nstep == 500
    assert config.calibration_metropolis_hastings.nskip == 5
    assert config.calibration_simplex.fuq_n == 8


def test_legacy_migration_restores_default_kind_and_temporal_list_alias() -> None:
    single = migrate_configuration_payload({"lpm": {"model_name": "exp"}})
    assert single["workflow"] == {"kind": "single_date"}
    assert single["lpm"]["models"] == ["exp"]

    temporal = migrate_configuration_payload(
        {
            "workflow": {"kind": "temporal"},
            "lpm_models": {"list": ["exp"]},
        }
    )
    assert temporal["lpm"]["models"] == ["exp"]


def test_schema_2_rejects_mixed_legacy_sections() -> None:
    with pytest.raises(ValueError, match="legacy top-level"):
        normalize_configuration_payload(
            {
                "schema_version": 2,
                "workflow": {"kind": "temporal"},
                "data": {"file": "observations.tsv"},
                "lpm_models": {"models": ["exp"]},
            }
        )
