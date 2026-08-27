# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Analytical tests for explicit radioactive-decay conventions."""

from pathlib import Path

import numpy as np
import pytest

from pyages.tracer.decay import rate_from_config, rate_from_half_life
from pyages.tracer.tracer_root import Tracer, TracerConfigError


def _write_tracer(root: Path, name: str, lines: list[str]) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / f"{name}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_half_life_reduces_constant_recharge_by_half(tmp_path):
    root = tmp_path / "tracers"
    _write_tracer(
        root,
        "radioactive",
        [
            "unit: arbitrary",
            "recharge_constant: 100",
            "half_life: 12.32",
            "datemin: 1900",
            "datemax: 2100",
        ],
    )
    tracer = Tracer(root, "radioactive")

    assert tracer.get_concentration(2000.0, 0.0) == pytest.approx(100.0)
    assert tracer.get_concentration(2000.0, 12.32) == pytest.approx(50.0)
    assert tracer.get_concentration(2000.0, 24.64) == pytest.approx(25.0)


def test_mean_lifetime_reduces_constant_recharge_by_e(tmp_path):
    root = tmp_path / "tracers"
    _write_tracer(
        root,
        "radioactive",
        [
            "unit: arbitrary",
            "recharge_constant: 100",
            "decay_mean_lifetime: 20",
            "datemin: 1900",
            "datemax: 2100",
        ],
    )
    tracer = Tracer(root, "radioactive")

    assert tracer.get_concentration(2000.0, 20.0) == pytest.approx(100.0 / np.e)


def test_production_with_decay_has_expected_asymptote(tmp_path):
    root = tmp_path / "tracers"
    half_life = 10.0
    production_rate = 2.0
    _write_tracer(
        root,
        "produced",
        [
            "unit: arbitrary",
            f"production_rate: {production_rate}",
            f"half_life: {half_life}",
            "datemin: 1900",
            "datemax: 2100",
        ],
    )
    tracer = Tracer(root, "produced")
    beta = rate_from_half_life(half_life)

    assert tracer.get_concentration(2000.0, 1000.0) == pytest.approx(
        production_rate / beta
    )


@pytest.mark.parametrize("value", [0, -1])
def test_decay_parameters_must_be_positive(value):
    with pytest.raises(ValueError):
        rate_from_config({"half_life": value})
    with pytest.raises(ValueError):
        rate_from_config({"decay_mean_lifetime": value})


def test_decay_conventions_are_mutually_exclusive():
    with pytest.raises(ValueError, match="only half_life or decay_mean_lifetime"):
        rate_from_config({"half_life": 10, "decay_mean_lifetime": 20})


def test_unknown_scalar_config_key_is_rejected(tmp_path):
    root = tmp_path / "tracers"
    _write_tracer(
        root,
        "invalid",
        [
            "unit: arbitrary",
            "recharge_constant: 100",
            "unsupported_decay_parameter: 10",
            "datemin: 1900",
            "datemax: 2100",
        ],
    )

    with pytest.raises(
        TracerConfigError,
        match="Unknown parameter in invalid.yaml: 'unsupported_decay_parameter'",
    ):
        Tracer(root, "invalid")
