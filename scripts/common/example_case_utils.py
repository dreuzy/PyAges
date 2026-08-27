# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Shared helpers for example case modules.

Purpose
-------
Keep the light orchestration/config plumbing reused by examples in one place:
- repository root resolution from a module path,
- YAML dict loading/dumping,
- recursive dict updates for generated configs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def repo_root_from(anchor: str | Path, levels_up: int = 3) -> Path:
    """
    Resolve the repository root by walking up from a file path.

    Parameters
    ----------
    anchor : str or Path
        File path used as the starting point.
    levels_up : int, optional
        Number of parent levels to traverse. Defaults to 3, which matches the
        example modules located under ``examples/<group>/<case>/``.
    """
    return Path(anchor).resolve().parents[levels_up]


def load_yaml_dict(path: Path) -> dict[str, Any]:
    """
    Load a YAML file and guarantee a mapping payload.
    """
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML structure in {path}")
    return payload


def dump_yaml_dict(path: Path, payload: dict[str, Any]) -> None:
    """
    Write a YAML mapping to disk, creating parent directories when needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively update nested mappings in-place and return the base mapping.
    """
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


__all__ = [
    "deep_update",
    "dump_yaml_dict",
    "load_yaml_dict",
    "repo_root_from",
]
