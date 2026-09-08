# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Direct contracts for the only executable configuration schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pyages.config.models import SingleDateConfig, TemporalConfig, TemporalLpmCfg
from pyages.config.paths import DIRECTORY_LPM_DATA
from pyages.workflows.single_date.config import load_config_payload


def test_schema_3_single_date_uses_common_sections(tmp_path: Path) -> None:
    payload = {
        "schema_version": 3,
        "workflow": {"kind": "single_date"},
        "data": {"name": "observations.tsv", "data_dir": "data"},
        "lpm": {"models": ["exp_shifted"]},
        "calibration": {
            "metropolis_hastings": {"nsteps": 321, "thinning": 3},
            "simplex": {"fuq_n": 7},
        },
        "output": {"use_default": False, "directory": "results"},
    }

    config = load_config_payload(tmp_path, payload)

    assert config.schema_version == 3
    assert config.data.data_dir == tmp_path / "data"
    assert config.lpm.models == ["exp_shifted"]
    assert config.lpm.directory == DIRECTORY_LPM_DATA
    assert config.calibration.metropolis_hastings.nsteps == 321
    assert config.calibration.metropolis_hastings.thinning == 3
    assert config.calibration.simplex.fuq_n == 7
    assert config.output.directory == tmp_path / "results"


def test_schema_3_temporal_uses_common_sections() -> None:
    config = TemporalConfig.model_validate(
        {
            "schema_version": 3,
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
    )

    assert config.schema_version == 3
    assert config.data.file == "data/observations.tsv"
    assert config.lpm.models == ["ig"]
    assert config.calibration.metropolis_hastings.nsteps == 401
    assert config.calibration.metropolis_hastings.thinning == 4
    assert config.calibration.metropolis_hastings.seed == 19
    assert config.reporting.temporal is True
    assert config.output.study_name == "audit"


@pytest.mark.parametrize("version", [1, 2, 4, "3", True, None])
def test_only_schema_3_is_accepted(version: object) -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        SingleDateConfig.model_validate(
            {
                "schema_version": version,
                "workflow": {"kind": "single_date"},
            }
        )


def test_schema_version_is_required() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        SingleDateConfig.model_validate({"workflow": {"kind": "single_date"}})


def test_removed_section_and_field_names_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_config_payload(
            tmp_path,
            {
                "schema_version": 3,
                "workflow": {"kind": "single_date"},
                "dataset": {"name": "observations.tsv"},
            },
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TemporalLpmCfg.model_validate({"list": ["exp"]})


def test_single_date_schema_requires_exactly_one_lpm() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        SingleDateConfig.model_validate(
            {
                "schema_version": 3,
                "workflow": {"kind": "single_date"},
                "lpm": {"models": ["exp", "ig"]},
            }
        )
