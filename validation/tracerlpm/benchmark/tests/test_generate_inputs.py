# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

from pathlib import Path

import numpy as np
import yaml

from validation.tracerlpm.benchmark.scripts.generate_inputs import (
    build_series,
    generate,
)


def test_input_shapes_and_defining_properties():
    config_path = Path(__file__).parents[1] / "configs" / "campaign.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    years, series = build_series(config)
    assert years.size == 126 * 12
    assert set(series) == {
        "constant",
        "ramp",
        "step",
        "rectangular_pulse",
        "multi_peak",
    }
    assert np.all(series["constant"] == 100)
    assert np.all(np.diff(series["ramp"]) >= 0)
    assert series["step"][years < 1960].max() == 0
    assert series["step"][years >= 1960].min() == 100
    assert series["rectangular_pulse"][(years >= 1960) & (years < 1965)].min() == 100
    assert np.all(series["multi_peak"] >= 0)


def test_generation_is_byte_reproducible(tmp_path):
    config_path = Path(__file__).parents[1] / "configs" / "campaign.yaml"
    first = generate(config_path, tmp_path / "one", tmp_path / "one.yaml")
    second = generate(config_path, tmp_path / "two", tmp_path / "two.yaml")
    assert [item["sha256"] for item in first["files"]] == [
        item["sha256"] for item in second["files"]
    ]
    assert [item["rows"] for item in first["files"]] == [1512] * 5
