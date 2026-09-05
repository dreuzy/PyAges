# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file loads, validates, and caches the parameter definition of an LPM.

"""Load and cache validated LPM parameter definitions.

Schema validation is implemented by
:mod:`pyages.data_io._lpm_parameter_schema`. This module adds filesystem access,
content-keyed caching, and focused accessors for consumers.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pyages.data_io._lpm_parameter_schema import (
    LPMParameterDefinition as LPMParameterDefinition,
)
from pyages.data_io._lpm_parameter_schema import (
    LPMParameterDomain,
    LPMParameterSchema,
    LPMParamsError,
    _thaw,
    parse_parameter_schema,
)


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    """One parsed file and the exact byte content for which it is valid."""

    fingerprint: bytes
    document: dict[str, Any]
    schema: LPMParameterSchema


_PARAMS_CACHE: dict[Path, _CacheEntry] = {}
_PARAMS_CACHE_LOCK = threading.RLock()


def _params_path(model_name: str, data_dir: str | Path) -> Path:
    """Return a normalized absolute path for one parameter file."""
    return (Path(data_dir) / model_name / "params.yaml").resolve()


def _read_parameter_bytes(path: Path) -> bytes:
    """Read one parameter file and normalize filesystem errors."""
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise LPMParamsError(f"Missing params.yaml: {path}") from exc
    except OSError as exc:
        raise LPMParamsError(f"Cannot read params.yaml: {path}") from exc


def _read_cache_entry(model_name: str, data_dir: str | Path) -> _CacheEntry:
    """Return a cache entry matching the file's exact current content."""
    path = _params_path(model_name, data_dir)
    content = _read_parameter_bytes(path)
    with _PARAMS_CACHE_LOCK:
        cached = _PARAMS_CACHE.get(path)
        if cached is not None and cached.fingerprint == content:
            return cached

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LPMParamsError(f"params.yaml is not valid UTF-8: {path}") from exc
    try:
        document = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise LPMParamsError(f"Malformed params.yaml: {path}") from exc
    if not isinstance(document, dict):
        raise LPMParamsError(f"{model_name}: params.yaml root must be a mapping")
    schema = parse_parameter_schema(document, expected_model=model_name)

    entry = _CacheEntry(
        fingerprint=content,
        document=document,
        schema=schema,
    )
    with _PARAMS_CACHE_LOCK:
        current = _PARAMS_CACHE.get(path)
        if current is not None and current.fingerprint == content:
            return current
        _PARAMS_CACHE[path] = entry
    return entry


def clear_params_cache() -> None:
    """Discard all content-keyed parameter documents and validated schemas."""
    with _PARAMS_CACHE_LOCK:
        _PARAMS_CACHE.clear()


def load_params(model_name: str, data_dir: str | Path) -> dict[str, Any]:
    """Load a validated ``params.yaml`` document and return a defensive copy.

    Cache reuse requires byte-for-byte identical UTF-8 file content; file
    timestamps and sizes are not used as freshness indicators.
    """
    return copy.deepcopy(_read_cache_entry(model_name, data_dir).document)


def load_parameter_schema(
    model_name: str,
    data_dir: str | Path,
) -> LPMParameterSchema:
    """Load one validated, immutable LPM parameter schema."""
    return _read_cache_entry(model_name, data_dir).schema


def get_calibration_ranges(
    schema: LPMParameterSchema,
) -> dict[str, tuple[float, float]]:
    """Return explicit operational calibration ranges by parameter name."""
    return {
        parameter.name: parameter.calibration_range for parameter in schema.parameters
    }


def get_domains(
    schema: LPMParameterSchema,
) -> dict[str, LPMParameterDomain]:
    """Return mathematical validity domains by parameter name."""
    return {parameter.name: parameter.domain for parameter in schema.parameters}


def get_init(
    schema: LPMParameterSchema,
) -> dict[str, float]:
    """Return ``{parameter_name: initial_value}``."""
    return {parameter.name: parameter.init for parameter in schema.parameters}


def get_steps(
    schema: LPMParameterSchema,
) -> dict[str, float]:
    """Return configured proposal steps, omitting parameters without one."""
    return {
        parameter.name: parameter.step
        for parameter in schema.parameters
        if parameter.step is not None
    }


def get_priors(
    schema: LPMParameterSchema,
) -> dict[str, dict[str, Any]]:
    """Return defensive copies of configured prior mappings."""
    return {
        parameter.name: _thaw(parameter.prior)
        for parameter in schema.parameters
        if parameter.prior is not None
    }


__all__ = [
    "LPMParameterDefinition",
    "LPMParameterDomain",
    "LPMParameterSchema",
    "LPMParamsError",
    "clear_params_cache",
    "get_calibration_ranges",
    "get_domains",
    "get_init",
    "get_priors",
    "get_steps",
    "load_parameter_schema",
    "load_params",
    "parse_parameter_schema",
]
