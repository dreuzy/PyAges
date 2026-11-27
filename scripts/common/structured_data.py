# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validate the small structural boundaries shared by repository tooling."""

from __future__ import annotations

from collections.abc import Mapping


def require_mapping(value: object, context: str) -> dict[str, object]:
    """Return a string-keyed mapping or raise a contextual format error."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{context} keys must be strings")
        result[key] = item
    return result


def require_list(value: object, context: str) -> list[object]:
    """Return a JSON-style list or raise a contextual format error."""
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return list(value)


def mapping_field(payload: Mapping[str, object], key: str) -> dict[str, object]:
    """Return one required mapping field."""
    if key not in payload:
        raise ValueError(f"Missing required field: {key}")
    return require_mapping(payload[key], key)


def list_field(payload: Mapping[str, object], key: str) -> list[object]:
    """Return one required list field."""
    if key not in payload:
        raise ValueError(f"Missing required field: {key}")
    return require_list(payload[key], key)


def string_field(payload: Mapping[str, object], key: str) -> str:
    """Return one required string field."""
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def integer_field(payload: Mapping[str, object], key: str) -> int:
    """Return one required integer field, excluding YAML/JSON booleans."""
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


__all__ = [
    "integer_field",
    "list_field",
    "mapping_field",
    "require_list",
    "require_mapping",
    "string_field",
]
