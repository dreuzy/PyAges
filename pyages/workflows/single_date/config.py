# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file reads a single-date YAML mapping relative to its configuration root
# and validates it with the launcher schema. It returns resolved dataset, model,
# result-path, and calibration settings, with clear errors for invalid input.

"""Configuration adapter for the single-date workflow."""

from pathlib import Path

from pydantic import ValidationError

from pyages.config.loading import load_yaml_mapping
from pyages.config.models import LauncherConfig


def load_config_payload(root_dir: Path, data: dict) -> LauncherConfig:
    """Validate a single-date mapping and preserve its nested YAML structure."""
    try:
        return LauncherConfig.model_validate(data, context={"root_dir": root_dir})
    except ValidationError as exc:
        raise ValueError(f"Invalid single-date workflow configuration:\n{exc}") from exc


def load_config(root_dir: Path, params_path: Path) -> LauncherConfig:
    """Load the canonical nested configuration used by the workflow."""
    return load_config_payload(root_dir, load_yaml_mapping(params_path))


__all__ = ["load_config", "load_config_payload"]
