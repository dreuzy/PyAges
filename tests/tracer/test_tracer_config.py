# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for typed tracer configuration loading."""

from __future__ import annotations

import pytest

from pyages.tracer.config import TracerConfig, load_tracer_config
from pyages.tracer.errors import TracerConfigError, TracerDataError


def test_mapping_is_normalized_and_metadata_is_ignored() -> None:
    config = TracerConfig.from_mapping(
        "sample",
        {
            "unit": "TU",
            "recharge_constant": "2.5",
            "production_rate": 0,
            "half_life": 10,
            "datemin": 1900,
            "datemax": 2100,
            "metadata": {"source": "test"},
        },
    )

    assert config.unit == "TU"
    assert config.recharge_constant == pytest.approx(2.5)
    assert config.production_rate == pytest.approx(0.0)
    assert config.decay_rate == pytest.approx(0.06931471805599453)
    assert config.datemin == pytest.approx(1900.0)
    assert config.datemax == pytest.approx(2100.0)


def test_numeric_fields_report_the_tracer_and_field() -> None:
    with pytest.raises(
        TracerConfigError,
        match="Tracer sample: recharge_constant must be numeric",
    ):
        TracerConfig.from_mapping("sample", {"recharge_constant": "many"})


def test_loader_distinguishes_invalid_yaml_from_invalid_configuration(tmp_path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("unit: [", encoding="utf-8")
    with pytest.raises(TracerDataError, match="Error parsing YAML"):
        load_tracer_config(malformed, "malformed")

    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("42\n", encoding="utf-8")
    with pytest.raises(TracerConfigError, match="must be a dictionary"):
        load_tracer_config(scalar, "scalar")


def test_loader_reports_a_missing_file(tmp_path) -> None:
    with pytest.raises(TracerDataError, match="YAML configuration file not found"):
        load_tracer_config(tmp_path / "missing.yaml", "missing")
