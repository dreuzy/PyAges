# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for LPM params.yaml loader."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from pyages.data_io import lpm_params


def _models() -> list[str]:
    return sorted(d.name for d in _data_dir().iterdir() if d.is_dir())


def _data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data_core" / "data_lpm"


@pytest.mark.parametrize("model_name", _models())
def test_load_params_smoke(model_name):
    params = lpm_params.load_params(model_name, _data_dir())
    assert params["model"] == model_name


@pytest.mark.parametrize("model_name", _models())
def test_bounds_init_steps_priors(model_name):
    schema = lpm_params.load_parameter_schema(model_name, _data_dir())
    bounds = lpm_params.get_bounds(schema)
    init = lpm_params.get_init(schema)
    steps = lpm_params.get_steps(schema)
    priors = lpm_params.get_priors(schema)

    assert bounds
    assert init
    assert steps
    assert priors


def _write_params(path: Path, *, initial: float = 10.0) -> None:
    model_dir = path / "custom"
    model_dir.mkdir(exist_ok=True)
    (model_dir / "params.yaml").write_text(
        f"""model: custom
parameters:
  - name: mu
    bounds: [0.1, 100.0]
    init: {initial}
    step: 1.0
    prior:
      type: uniform
      min: 0.1
      max: 100.0
""",
        encoding="utf-8",
    )


def test_load_parameter_schema_is_typed_and_immutable(tmp_path) -> None:
    _write_params(tmp_path)

    schema = lpm_params.load_parameter_schema("custom", tmp_path)

    assert schema.model == "custom"
    assert schema.version == 1
    assert schema.names == ("mu",)
    assert schema.parameters[0].bounds == (0.1, 100.0)
    assert schema.parameters[0].init == 10.0
    with pytest.raises(TypeError):
        schema.parameters[0].prior["type"] = "normal"


def test_load_params_returns_a_defensive_copy(tmp_path) -> None:
    _write_params(tmp_path)

    first = lpm_params.load_params("custom", tmp_path)
    first["parameters"][0]["init"] = 99.0

    second = lpm_params.load_params("custom", tmp_path)
    assert second["parameters"][0]["init"] == 10.0


def test_cache_invalidates_when_parameter_file_changes(tmp_path) -> None:
    _write_params(tmp_path, initial=10.0)
    assert (
        lpm_params.load_parameter_schema("custom", tmp_path).parameters[0].init == 10.0
    )

    _write_params(tmp_path, initial=25.25)

    assert (
        lpm_params.load_parameter_schema("custom", tmp_path).parameters[0].init == 25.25
    )


def test_cache_uses_content_when_size_and_timestamp_are_unchanged(tmp_path) -> None:
    _write_params(tmp_path, initial=10.0)
    path = tmp_path / "custom" / "params.yaml"
    assert (
        lpm_params.load_parameter_schema("custom", tmp_path).parameters[0].init == 10.0
    )
    original_stat = path.stat()

    _write_params(tmp_path, initial=20.0)
    assert path.stat().st_size == original_stat.st_size
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    assert (
        lpm_params.load_parameter_schema("custom", tmp_path).parameters[0].init == 20.0
    )


def test_resolved_paths_share_one_cached_parse(tmp_path, monkeypatch) -> None:
    _write_params(tmp_path)
    lpm_params.clear_params_cache()
    calls = 0
    real_safe_load = yaml.safe_load

    def counted_safe_load(stream):
        nonlocal calls
        calls += 1
        return real_safe_load(stream)

    monkeypatch.setattr(lpm_params.yaml, "safe_load", counted_safe_load)
    lpm_params.load_params("custom", tmp_path.resolve())
    monkeypatch.chdir(tmp_path.parent)
    lpm_params.load_parameter_schema("custom", Path(tmp_path.name))

    assert calls == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("step", 0.0, "strictly positive"),
        ("prior", "uniform", "must be a mapping"),
    ],
)
def test_shared_schema_rejects_invalid_optional_metadata(field, value, message) -> None:
    params = {
        "model": "custom",
        "parameters": [
            {
                "name": "mu",
                "bounds": [0.1, 100.0],
                "init": 10.0,
                field: value,
            }
        ],
    }

    with pytest.raises(lpm_params.LPMParamsError, match=message):
        lpm_params.parse_parameter_schema(params)


@pytest.mark.parametrize(
    ("prior", "message"),
    [
        ({"min": 0.0, "max": 1.0}, "must define a type"),
        (
            {"type": "gaussian", "mean": 0.0, "std": 1.0},
            "unsupported prior type",
        ),
        ({"type": "lognormal", "args": [0.0, 1.0]}, "unsupported prior type"),
        ({"type": "uniform", "min": 0.0}, "requires 'min' and 'max'"),
        (
            {"type": "uniform", "min": 1.0, "max": 1.0},
            "minimum must be lower than maximum",
        ),
        (
            {"type": "normal", "mean": 0.0},
            "requires 'mean' and 'std'",
        ),
        (
            {"type": "normal", "mean": 0.0, "std": 0.0},
            "strictly positive",
        ),
    ],
)
def test_schema_rejects_invalid_parametric_priors(prior, message) -> None:
    params = {
        "model": "custom",
        "parameters": [
            {
                "name": "mu",
                "bounds": [0.0, 1.0],
                "init": 0.5,
                "prior": prior,
            }
        ],
    }

    with pytest.raises(lpm_params.LPMParamsError, match=message):
        lpm_params.parse_parameter_schema(params)


def test_schema_accepts_normal_prior() -> None:
    params = {
        "model": "custom",
        "version": 1,
        "parameters": [
            {
                "name": "mu",
                "bounds": [0.0, 10.0],
                "init": 1.0,
                "prior": {"type": "normal", "mean": 2.0, "std": 0.5},
            }
        ],
    }

    schema = lpm_params.parse_parameter_schema(params)
    assert lpm_params.get_priors(schema)["mu"] == {
        "type": "normal",
        "mean": 2.0,
        "std": 0.5,
    }


@pytest.mark.parametrize("version", [0, 2, "1", True])
def test_schema_rejects_unsupported_versions(version) -> None:
    params = {
        "model": "custom",
        "version": version,
        "parameters": [{"name": "mu", "bounds": [0.0, 1.0], "init": 0.5}],
    }

    with pytest.raises(lpm_params.LPMParamsError, match="expected 1"):
        lpm_params.parse_parameter_schema(params)
