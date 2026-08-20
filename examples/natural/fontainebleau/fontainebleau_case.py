# -*- coding: utf-8 -*-
"""
Fontainebleau case helpers: paths, config loading, and shared dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from pyage.config.models import LauncherParams
from pyage.workflows.single_date_config import load_params
from scripts.common.example_case_utils import (
    deep_update,
    repo_root_from,
)
from scripts.common.example_case_utils import (
    dump_yaml_dict as dump_yaml,
)
from scripts.common.example_case_utils import (
    load_yaml_dict as load_yaml,
)
from scripts.common.example_launcher_utils import (
    build_effective_launcher_config,
    generated_launcher_config_path,
)
from scripts.common.launcher_paths import dataset_results_directory


@dataclass(frozen=True)
class FontainebleauPaths:
    repo_root: Path
    example_dir: Path
    data_dir: Path
    generated_dir: Path
    benchmark_dir: Path
    launcher_config_dir: Path
    yaml_path: Path
    notebook_path: Path


@dataclass(frozen=True)
class FontainebleauContext:
    paths: FontainebleauPaths
    config: dict[str, Any]
    params: LauncherParams
    dataset_path: Path
    available_datasets: list[str]
    available_lpm_models: list[str]
    expected_results_dir: Path


@dataclass
class PreparedFontainebleauCase:
    context: FontainebleauContext
    selected_observations: pd.DataFrame
    all_observations: pd.DataFrame
    dataset_summary: pd.DataFrame
    tracer_summary: pd.DataFrame


def repo_root() -> Path:
    return repo_root_from(__file__)


def resolve_paths(config_path: Path | None = None) -> FontainebleauPaths:
    root = repo_root()
    example_dir = Path(__file__).resolve().parent
    yaml_path = config_path or (example_dir / "exemple_fontainebleau.yaml")
    data_dir = example_dir / "data"
    generated_dir = example_dir / "generated"
    benchmark_dir = generated_dir / "benchmark"
    launcher_config_dir = generated_dir / "launcher_configs"
    return FontainebleauPaths(
        repo_root=root,
        example_dir=example_dir,
        data_dir=data_dir,
        generated_dir=generated_dir,
        benchmark_dir=benchmark_dir,
        launcher_config_dir=launcher_config_dir,
        yaml_path=yaml_path,
        notebook_path=example_dir / "benchmark_fontainebleau.ipynb",
    )


def load_fontainebleau_config(config_path: Path | None = None) -> dict[str, Any]:
    paths = resolve_paths(config_path)
    return load_yaml(paths.yaml_path)


def list_available_datasets(data_dir: Path) -> list[str]:
    if not data_dir.exists():
        return []
    return sorted(
        path.name
        for path in data_dir.iterdir()
        if path.is_file() and path.name.startswith("fontainebleau_")
    )


def list_available_lpm_models(lpm_dir: Path) -> list[str]:
    if not lpm_dir.exists():
        return []
    return sorted(path.name for path in lpm_dir.iterdir() if path.is_dir())


def expected_results_dir(dataset_name: str) -> Path:
    return dataset_results_directory(dataset_name)


def build_context(config_path: Path | None = None) -> FontainebleauContext:
    paths = resolve_paths(config_path)
    cfg = load_fontainebleau_config(paths.yaml_path)
    params = load_params(paths.repo_root, paths.yaml_path)
    dataset_path = params.dataset_data_dir / params.dataset_name
    if not dataset_path.exists():
        raise FileNotFoundError(f"Missing Fontainebleau dataset: {dataset_path}")
    return FontainebleauContext(
        paths=paths,
        config=cfg,
        params=params,
        dataset_path=dataset_path,
        available_datasets=list_available_datasets(params.dataset_data_dir),
        available_lpm_models=list_available_lpm_models(params.directory_lpm),
        expected_results_dir=expected_results_dir(params.dataset_name),
    )


def generated_config_path(
    context: FontainebleauContext,
    dataset_name: str | None = None,
    lpm_model_name: str | None = None,
) -> Path:
    return generated_launcher_config_path(
        context.paths.launcher_config_dir,
        dataset_name=dataset_name or context.params.dataset_name,
        lpm_model_name=lpm_model_name or context.params.lpm_model_name,
    )


def build_effective_config(
    config_path: Path | None = None,
    *,
    dataset_name: str | None = None,
    dataset_label: str | None = None,
    lpm_model_name: str | None = None,
    mh_nstep: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_fontainebleau_config(config_path)
    if dataset_name:
        existing_label = str(payload.get("dataset", {}).get("label", "")).strip()
        if dataset_label is None and (
            not existing_label or existing_label == "Fontainebleau single-date example"
        ):
            dataset_label = (
                f"Fontainebleau {dataset_name.removeprefix('fontainebleau_')}"
            )
    return build_effective_launcher_config(
        payload,
        dataset_name=dataset_name,
        dataset_label=dataset_label,
        lpm_model_name=lpm_model_name,
        mh_nstep=mh_nstep,
        overrides=overrides,
    )


def write_effective_config(
    context: FontainebleauContext,
    *,
    output_path: Path | None = None,
    dataset_name: str | None = None,
    dataset_label: str | None = None,
    lpm_model_name: str | None = None,
    mh_nstep: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> Path:
    out_path = output_path or generated_config_path(
        context,
        dataset_name=dataset_name,
        lpm_model_name=lpm_model_name,
    )
    payload = build_effective_config(
        context.paths.yaml_path,
        dataset_name=dataset_name,
        dataset_label=dataset_label,
        lpm_model_name=lpm_model_name,
        mh_nstep=mh_nstep,
        overrides=overrides,
    )
    dump_yaml(out_path, payload)
    return out_path


__all__ = [
    "FontainebleauContext",
    "FontainebleauPaths",
    "PreparedFontainebleauCase",
    "build_context",
    "build_effective_config",
    "deep_update",
    "dump_yaml",
    "expected_results_dir",
    "generated_config_path",
    "list_available_datasets",
    "list_available_lpm_models",
    "load_fontainebleau_config",
    "load_yaml",
    "repo_root",
    "resolve_paths",
    "write_effective_config",
]
