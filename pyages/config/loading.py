# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file reads a YAML file as a mapping and validates it against a requested
# Pydantic model. It also resolves referenced paths from a chosen base directory
# so every workflow reports missing files and invalid settings consistently.

"""Shared YAML loading and configuration path helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ValidationError

from pyages.config.models import CONFIGURATION_SCHEMA_VERSION


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a required YAML mapping with consistent errors."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Configuration file not found: {source}")
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a YAML mapping in {source}")
    return payload


def workflow_kind(payload: Mapping[str, Any]) -> Literal["single_date", "temporal"]:
    """Return the schema-3 workflow kind declared by a YAML mapping."""
    version = payload.get("schema_version")
    if version != CONFIGURATION_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be the integer {CONFIGURATION_SCHEMA_VERSION}"
        )
    workflow = payload.get("workflow")
    declared = workflow.get("kind") if isinstance(workflow, Mapping) else None
    if declared not in {"single_date", "temporal"}:
        raise ValueError(
            "workflow.kind is required and must be 'single_date' or 'temporal'"
        )
    return cast(Literal["single_date", "temporal"], declared)


def validate_yaml_model(
    path: str | Path,
    model_type: type[BaseModel],
    *,
    context: dict[str, Any] | None = None,
    label: str = "configuration",
) -> BaseModel:
    """Load a YAML mapping and validate it with a Pydantic model."""
    try:
        return model_type.model_validate(load_yaml_mapping(path), context=context)
    except ValidationError as exc:
        raise ValueError(f"Invalid {label}:\n{exc}") from exc


def resolve_from(base_directory: str | Path, value: str | Path) -> Path:
    """Resolve an absolute path or one relative to a configuration root."""
    path = Path(value)
    if not path.is_absolute():
        path = Path(base_directory) / path
    return path.resolve()


__all__ = ["load_yaml_mapping", "resolve_from", "validate_yaml_model", "workflow_kind"]
