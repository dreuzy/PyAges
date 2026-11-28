# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for unloaded entry-point discovery and external LPM construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

import pyages.lpm.core.registry as registry
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.extensions import LpmDefinition
from pyages.lpm.factory import build_lpm, list_available_lpms


class ExternalTestLpm(LpmBase):
    """Small uniform distribution used only at the plugin boundary."""

    def __init__(self, scale=10.0, directory_lpm=None):
        super().__init__(
            "external_test",
            {"scale": scale},
            {"scale": "year"},
            directory_lpm,
        )

    def pdf(self, t):
        values = np.asarray(t, dtype=float)
        result = np.where(
            (values >= 0.0) & (values <= self.p["scale"]),
            1.0 / self.p["scale"],
            0.0,
        )
        return float(result) if values.ndim == 0 else result

    def cdf(self, t):
        values = np.asarray(t, dtype=float)
        result = np.clip(values / self.p["scale"], 0.0, 1.0)
        return float(result) if values.ndim == 0 else result

    def mean(self):
        return self.p["scale"] / 2.0

    def std(self):
        return self.p["scale"] / np.sqrt(12.0)

    def cdf_and_partial_first_moment(self, t):
        values = np.asarray(t, dtype=float)
        bounded = np.clip(values, 0.0, self.p["scale"])
        cdf = bounded / self.p["scale"]
        moment = bounded**2 / (2.0 * self.p["scale"])
        if values.ndim == 0:
            return float(cdf), float(moment)
        return cdf, moment


@dataclass
class FakeEntryPoint:
    """Minimal importlib entry-point double with observable lazy loading."""

    name: str
    value: str
    loaded: object
    load_count: int = 0
    dist: object | None = None

    def load(self):
        self.load_count += 1
        return self.loaded


@pytest.fixture(autouse=True)
def isolated_external_catalog(monkeypatch):
    registry.discover_lpms()
    registry._reset_registry_state_for_tests()
    monkeypatch.setattr(registry, "_installed_entry_points", lambda: ())
    yield
    registry._reset_registry_state_for_tests()


def _parameter_root(tmp_path: Path, *, initial: float = 10.0) -> Path:
    root = tmp_path / f"parameters-{initial:g}"
    model = root / "external_test"
    model.mkdir(parents=True)
    (model / "params.yaml").write_text(
        f"""\
model: external_test
version: 1
parameters:
  - name: scale
    label: scale
    unit: year
    description: Uniform support.
    domain: {{min: 0.0, min_inclusive: false, max: null}}
    calibration_range: [1.0, 100.0]
    init: {initial}
    step: 1.0
    prior: {{type: uniform, min: 1.0, max: 100.0, unit: year}}
""",
        encoding="utf-8",
    )
    return root


def _advertise(monkeypatch, *entry_points: FakeEntryPoint) -> None:
    monkeypatch.setattr(
        registry,
        "_installed_entry_points",
        lambda: tuple(entry_points),
    )


def test_listing_reads_metadata_without_loading_plugin(monkeypatch, tmp_path) -> None:
    definition = LpmDefinition(ExternalTestLpm, _parameter_root(tmp_path))
    entry_point = FakeEntryPoint("external_test", "example.model:definition", definition)
    _advertise(monkeypatch, entry_point)

    assert "external_test" in list_available_lpms()
    assert entry_point.load_count == 0


def test_build_loads_once_and_uses_packaged_parameters(monkeypatch, tmp_path) -> None:
    parameter_root = _parameter_root(tmp_path)
    definition = LpmDefinition(ExternalTestLpm, parameter_root)
    entry_point = FakeEntryPoint("external_test", "example.model:definition", definition)
    _advertise(monkeypatch, entry_point)

    first = build_lpm("external_test")
    second = build_lpm("external_test")

    assert first.lpm_data_directory == parameter_root
    assert second.name == "external_test"
    assert entry_point.load_count == 1
    assert first.provenance is not None
    assert first.provenance.entry_point_target == "example.model:definition"
    assert len(first.provenance.parameters_sha256) == 64


def test_explicit_parameter_directory_has_priority(monkeypatch, tmp_path) -> None:
    packaged = _parameter_root(tmp_path / "packaged", initial=10.0)
    override = _parameter_root(tmp_path / "override", initial=20.0)
    entry_point = FakeEntryPoint(
        "external_test",
        "example.model:definition",
        LpmDefinition(ExternalTestLpm, packaged),
    )
    _advertise(monkeypatch, entry_point)

    model = build_lpm("external_test", directory_lpm=override)

    assert model.lpm_data_directory == override
    assert model.param_init() == [20.0]


def test_conflict_is_reported_without_loading_either_plugin(
    monkeypatch, tmp_path
) -> None:
    definition = LpmDefinition(ExternalTestLpm, _parameter_root(tmp_path))
    first = FakeEntryPoint("external_test", "one:definition", definition)
    second = FakeEntryPoint("external_test", "two:definition", definition)
    _advertise(monkeypatch, first, second)

    assert "external_test" not in list_available_lpms()
    item = next(item for item in registry.list_lpm_catalog() if item.name == "external_test")
    assert item.status == "conflict"
    with pytest.raises(registry.LpmNameConflict, match="provided more than once"):
        build_lpm("external_test")
    assert first.load_count == second.load_count == 0


def test_incompatible_plugin_api_is_rejected(monkeypatch, tmp_path) -> None:
    entry_point = FakeEntryPoint(
        "external_test",
        "example.model:definition",
        LpmDefinition(ExternalTestLpm, _parameter_root(tmp_path), api_version=999),
    )
    _advertise(monkeypatch, entry_point)

    with pytest.raises(registry.InvalidLpmPlugin, match="api_version=999"):
        build_lpm("external_test")
