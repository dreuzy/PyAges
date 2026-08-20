# -*- coding: utf-8 -*-
"""
Shared helpers for generated single-date launcher configurations.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pyage.config.models import LauncherConfig
from scripts.common.example_case_utils import deep_update


def _tokenize(value: str) -> str:
    return value.replace("\\", "_").replace("/", "_")


def generated_launcher_config_path(
    output_dir: Path,
    *,
    dataset_name: str,
    lpm_model_name: str | None = None,
) -> Path:
    """
    Build a stable output filename for a generated launcher YAML.
    """
    dataset_token = _tokenize(dataset_name)
    if lpm_model_name:
        lpm_token = _tokenize(lpm_model_name)
        filename = f"{dataset_token}_{lpm_token}_launcher.yaml"
    else:
        filename = f"{dataset_token}_launcher.yaml"
    return output_dir / filename


def build_effective_launcher_config(
    base_config: dict[str, Any],
    *,
    dataset_name: str | None = None,
    dataset_label: str | None = None,
    dataset_year: int | None = None,
    dataset_data_dir: str | Path | None = None,
    dataset_verbose: bool | None = None,
    lpm_model_name: str | None = None,
    lpm_data_directory: str | Path | None = None,
    tracer_data_dir: str | Path | None = None,
    mh_nstep: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Apply common single-date launcher overrides on top of a base YAML payload.
    """
    payload = copy.deepcopy(base_config)
    dataset_cfg = payload.setdefault("dataset", {})
    lpm_cfg = payload.setdefault("lpm", {})
    mh_cfg = payload.setdefault("calibration_metropolis_hastings", {})

    _update_defined(
        dataset_cfg,
        name=dataset_name,
        label=dataset_label,
        year=None if dataset_year is None else int(dataset_year),
        data_dir=None if dataset_data_dir is None else str(dataset_data_dir),
        verbose=None if dataset_verbose is None else bool(dataset_verbose),
    )
    _update_defined(
        lpm_cfg,
        model_name=lpm_model_name,
        data_directory=(
            None if lpm_data_directory is None else str(lpm_data_directory)
        ),
    )

    if tracer_data_dir is not None:
        tracer_cfg = payload.setdefault("tracers", {})
        tracer_cfg["data_directory"] = str(tracer_data_dir)

    if mh_nstep is not None:
        mh_cfg["nstep"] = int(mh_nstep)

    if overrides:
        deep_update(payload, copy.deepcopy(overrides))
    LauncherConfig.model_validate(payload)
    return payload


def _update_defined(target: dict[str, Any], **values: Any) -> None:
    """Update a mapping without replacing defaults with ``None``."""
    target.update({key: value for key, value in values.items() if value is not None})


__all__ = [
    "build_effective_launcher_config",
    "generated_launcher_config_path",
]
