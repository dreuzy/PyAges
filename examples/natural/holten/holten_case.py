# -*- coding: utf-8 -*-
"""
Holten case helpers: paths, config loading, and shared dataclasses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()

from pyage.config.models import LauncherParams
from scripts.common.example_case_utils import (
    dump_yaml_dict as dump_yaml,
    load_yaml_dict as load_yaml,
    repo_root_from,
)
from scripts.common.example_launcher_utils import (
    build_effective_launcher_config,
    generated_launcher_config_path,
)
from scripts.common.launcher_params import load_params


@dataclass(frozen=True)
class HoltenPaths:
    repo_root: Path
    example_dir: Path
    data_dir: Path
    doc_dir: Path
    generated_dir: Path
    launcher_config_dir: Path
    tracer_source_dir: Path
    prepared_tracer_dir: Path
    lpm_data_dir: Path
    yaml_path: Path
    sampling_raw_path: Path
    tritium_raw_path: Path
    kr85_raw_path: Path
    reference_results_path: Path
    aggregated_dataset_path: Path
    benchmark_dir: Path


@dataclass(frozen=True)
class HoltenContext:
    paths: HoltenPaths
    config: dict[str, Any]
    params: LauncherParams
    tracer_source_dirs: dict[str, Path]
    selected_wells: list[str]
    calibration_tracers: list[str]
    date_round_decimals: int
    lpm_name: str
    launcher_enabled: bool
    launcher_inline: bool
    generate_per_well_files: bool

    def with_selected_wells(self, selected_wells: list[str]) -> "HoltenContext":
        normalized = [str(well_id) for well_id in selected_wells]
        unknown = sorted(set(normalized).difference(self.selected_wells))
        if unknown:
            raise ValueError(f"Unknown Holten wells requested: {unknown}")
        return replace(self, selected_wells=normalized)


@dataclass
class PreparedHoltenCase:
    context: HoltenContext
    sampling_raw: pd.DataFrame
    observed_aggregated: pd.DataFrame
    observed_by_well: dict[str, pd.DataFrame]
    tracer_histories: dict[str, pd.DataFrame]
    preparation_log: pd.DataFrame
    helium_diagnostics: pd.DataFrame

    def subset(self, selected_wells: list[str]) -> "PreparedHoltenCase":
        context = self.context.with_selected_wells(selected_wells)
        selected = set(context.selected_wells)
        return PreparedHoltenCase(
            context=context,
            sampling_raw=self.sampling_raw.loc[self.sampling_raw["ID"].isin(selected)].copy().reset_index(drop=True),
            observed_aggregated=self.observed_aggregated.loc[
                self.observed_aggregated["well_id"].isin(selected)
            ].copy().reset_index(drop=True),
            observed_by_well={
                well_id: frame.copy().reset_index(drop=True)
                for well_id, frame in self.observed_by_well.items()
                if well_id in selected
            },
            tracer_histories={
                tracer_name: frame.copy().reset_index(drop=True)
                for tracer_name, frame in self.tracer_histories.items()
            },
            preparation_log=self.preparation_log.loc[
                self.preparation_log["well_id"].isin(selected)
            ].copy().reset_index(drop=True),
            helium_diagnostics=self.helium_diagnostics.loc[
                self.helium_diagnostics["well_id"].isin(selected)
            ].copy().reset_index(drop=True),
        )


def repo_root() -> Path:
    return repo_root_from(__file__)


def _resolve_repo_relative(path_value: str | Path, root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root / path


def _common_parent(paths: list[Path], fallback: Path) -> Path:
    if not paths:
        return fallback
    return Path(os.path.commonpath([str(path.resolve()) for path in paths]))


def resolve_paths(config_path: Path | None = None) -> HoltenPaths:
    root = repo_root()
    example_dir = Path(__file__).resolve().parent
    yaml_path = Path(config_path) if config_path is not None else (example_dir / "holten.yaml")
    cfg = load_yaml(yaml_path)
    params = load_params(root, yaml_path)
    holten_cfg = cfg.get("holten", {})
    tracer_cfg = holten_cfg.get("tracers", {})
    prep_cfg = holten_cfg.get("preparation", {})
    validation_cfg = holten_cfg.get("validation", {})

    data_dir = params.dataset_data_dir
    lpm_data_dir = params.directory_lpm
    prepared_tracer_dir = (
        params.tracer_data_dir
        if params.tracer_data_dir is not None
        else _resolve_repo_relative(
            tracer_cfg.get("prepared_data_dir", example_dir / "prepared_tracers" / "data_tracer"),
            root,
        )
    )
    sampling_raw_path = _resolve_repo_relative(
        prep_cfg.get("source_sampling_file", example_dir / "doc" / "sampling_data.txt"),
        root,
    )
    tritium_raw_path = _resolve_repo_relative(
        prep_cfg.get("source_tritium_file", example_dir / "doc" / "local_tritium.txt"),
        root,
    )
    kr85_raw_path = _resolve_repo_relative(
        prep_cfg.get("source_kr85_file", example_dir / "doc" / "freiburg_krypton.txt"),
        root,
    )
    reference_results_path = _resolve_repo_relative(
        validation_cfg.get("reference_results", example_dir / "doc" / "calibration_results.txt"),
        root,
    )
    aggregated_dataset_path = _resolve_repo_relative(
        prep_cfg.get("aggregated_dataset", data_dir / "holten_2010_selected_wells.txt"),
        root,
    )
    tracer_source_paths = [
        _resolve_repo_relative(path_text, root)
        for path_text in tracer_cfg.get("source_directories", {}).values()
    ]
    doc_dir = _common_parent(
        [sampling_raw_path, tritium_raw_path, kr85_raw_path, reference_results_path],
        example_dir / "doc",
    )
    generated_dir = example_dir / "generated"
    launcher_config_dir = generated_dir / "launcher_configs"
    tracer_source_dir = _common_parent(tracer_source_paths, example_dir / "tracers")
    benchmark_dir = generated_dir / "benchmark"
    return HoltenPaths(
        repo_root=root,
        example_dir=example_dir,
        data_dir=data_dir,
        doc_dir=doc_dir,
        generated_dir=generated_dir,
        launcher_config_dir=launcher_config_dir,
        tracer_source_dir=tracer_source_dir,
        prepared_tracer_dir=prepared_tracer_dir,
        lpm_data_dir=lpm_data_dir,
        yaml_path=yaml_path,
        sampling_raw_path=sampling_raw_path,
        tritium_raw_path=tritium_raw_path,
        kr85_raw_path=kr85_raw_path,
        reference_results_path=reference_results_path,
        aggregated_dataset_path=aggregated_dataset_path,
        benchmark_dir=benchmark_dir,
    )


def load_holten_config(config_path: Path | None = None) -> dict[str, Any]:
    paths = resolve_paths(config_path)
    return load_yaml(paths.yaml_path)


def build_context(config_path: Path | None = None) -> HoltenContext:
    paths = resolve_paths(config_path)
    cfg = load_holten_config(paths.yaml_path)
    params = load_params(paths.repo_root, paths.yaml_path)
    holten_cfg = cfg.get("holten", {})
    campaign_cfg = holten_cfg.get("campaign", {})
    tracer_cfg = holten_cfg.get("tracers", {})
    prep_cfg = holten_cfg.get("preparation", {})
    launcher_cfg = holten_cfg.get("launcher", {})
    selected_wells = [str(w) for w in campaign_cfg.get("selected_wells", [])]
    calibration_tracers = [str(t) for t in tracer_cfg.get("calibration", [])]
    tracer_source_dirs: dict[str, Path] = {}
    source_directories = tracer_cfg.get("source_directories", {})
    for tracer_name in calibration_tracers:
        configured = source_directories.get(tracer_name)
        tracer_source_dirs[tracer_name] = (
            _resolve_repo_relative(configured, paths.repo_root)
            if configured is not None
            else paths.tracer_source_dir / tracer_name
        )
    return HoltenContext(
        paths=paths,
        config=cfg,
        params=params,
        tracer_source_dirs=tracer_source_dirs,
        selected_wells=selected_wells,
        calibration_tracers=calibration_tracers,
        date_round_decimals=int(prep_cfg.get("date_round_decimals", 5)),
        lpm_name=params.lpm_model_name,
        launcher_enabled=bool(launcher_cfg.get("enabled", False)),
        launcher_inline=bool(launcher_cfg.get("inline", False)),
        generate_per_well_files=bool(prep_cfg.get("generate_per_well_files", True)),
    )


def tracer_yaml_path(context: HoltenContext, tracer_name: str) -> Path:
    tracer_dir = context.tracer_source_dirs.get(tracer_name, context.paths.tracer_source_dir / tracer_name)
    return tracer_dir / f"{tracer_name}.yaml"


def generated_config_path(
    context: HoltenContext,
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
    dataset_year: int | None = None,
    dataset_data_dir: str | Path | None = None,
    dataset_verbose: bool | None = None,
    lpm_model_name: str | None = None,
    lpm_data_directory: str | Path | None = None,
    tracer_data_dir: str | Path | None = None,
    mh_nstep: int | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_holten_config(config_path)
    return build_effective_launcher_config(
        payload,
        dataset_name=dataset_name,
        dataset_label=dataset_label,
        dataset_year=dataset_year,
        dataset_data_dir=dataset_data_dir,
        dataset_verbose=dataset_verbose,
        lpm_model_name=lpm_model_name,
        lpm_data_directory=lpm_data_directory,
        tracer_data_dir=tracer_data_dir,
        mh_nstep=mh_nstep,
        overrides=overrides,
    )


def write_effective_config(
    context: HoltenContext,
    *,
    output_path: Path | None = None,
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
        dataset_year=dataset_year,
        dataset_data_dir=dataset_data_dir,
        dataset_verbose=dataset_verbose,
        lpm_model_name=lpm_model_name,
        lpm_data_directory=lpm_data_directory,
        tracer_data_dir=tracer_data_dir,
        mh_nstep=mh_nstep,
        overrides=overrides,
    )
    dump_yaml(out_path, payload)
    return out_path


def write_well_launcher_config(context: HoltenContext, well_id: str) -> Path:
    if not context.generate_per_well_files:
        raise ValueError(
            "Holten launcher configs require "
            "`holten.preparation.generate_per_well_files: true` "
            "because launcher runs target per-well datasets."
        )
    dataset_name = f"holten_2010_{well_id}.txt"
    return write_effective_config(
        context,
        output_path=context.paths.launcher_config_dir / f"holten_{well_id}_launcher.yaml",
        dataset_name=dataset_name,
        dataset_label=f"Holten {well_id}",
        dataset_year=context.params.dataset_year,
        dataset_data_dir=context.paths.data_dir.relative_to(context.paths.repo_root),
        dataset_verbose=True,
        lpm_model_name=context.params.lpm_model_name,
        lpm_data_directory=context.paths.lpm_data_dir.relative_to(context.paths.repo_root),
        tracer_data_dir=context.paths.prepared_tracer_dir.relative_to(context.paths.repo_root),
    )


def parse_dd_mm_yy(date_text: str) -> datetime:
    day_text, month_text, year_text = [part.strip() for part in date_text.split("-")]
    year_2d = int(year_text)
    year = 2000 + year_2d if year_2d <= 49 else 1900 + year_2d
    return datetime(year, int(month_text), int(day_text), tzinfo=timezone.utc)


def decimal_year_from_sampling_date(date_text: str) -> float:
    dt = parse_dd_mm_yy(date_text)
    year_start = datetime(dt.year, 1, 1, tzinfo=timezone.utc)
    next_year = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    return dt.year + (dt - year_start).total_seconds() / (next_year - year_start).total_seconds()


def rounded_decimal_year(date_text: str, ndigits: int = 5) -> float:
    return round(decimal_year_from_sampling_date(date_text), ndigits)
