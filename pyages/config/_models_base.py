# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file supplies the strict base class and field validators reused by all
# configuration models. It rejects unknown keys and boolean numbers, and turns
# relative path inputs into paths rooted at the active configuration directory.

"""Shared strict base and validators for user-facing configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


def resolve_path(value: Path, info):
    """Resolve one relative configuration path against the validation context."""
    root_dir = info.context.get("root_dir") if info.context else None
    if root_dir and not value.is_absolute():
        return Path(root_dir) / value
    return value


def reject_boolean_number(value: object, info):
    """Reject YAML booleans before Pydantic can coerce them to zero or one."""
    if isinstance(value, bool):
        raise ValueError(f"{info.field_name} must be numeric, not boolean")
    return value


class BaseConfigModel(BaseModel):
    """Strict base for all user-facing configuration models."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


__all__ = ["BaseConfigModel", "reject_boolean_number", "resolve_path"]
