# -*- coding: utf-8 -*-
"""
Shared helpers for generated single-date launcher configurations.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

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

    if dataset_name is not None:
        dataset_cfg["name"] = dataset_name
    if dataset_label is not None:
        dataset_cfg["label"] = dataset_label
    if dataset_year is not None:
        dataset_cfg["year"] = int(dataset_year)
    if dataset_data_dir is not None:
        dataset_cfg["data_dir"] = str(dataset_data_dir)
    if dataset_verbose is not None:
        dataset_cfg["verbose"] = bool(dataset_verbose)

    if lpm_model_name is not None:
        lpm_cfg["model_name"] = lpm_model_name
    if lpm_data_directory is not None:
        lpm_cfg["data_directory"] = str(lpm_data_directory)

    if tracer_data_dir is not None:
        tracer_cfg = payload.setdefault("tracers", {})
        tracer_cfg["data_directory"] = str(tracer_data_dir)

    if mh_nstep is not None:
        mh_cfg["nstep"] = int(mh_nstep)

    if overrides:
        deep_update(payload, copy.deepcopy(overrides))
    return payload


__all__ = [
    "build_effective_launcher_config",
    "generated_launcher_config_path",
]
