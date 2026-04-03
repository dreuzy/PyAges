# -*- coding: utf-8 -*-
"""
Holten case helpers: paths, config loading, and shared dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

import pandas as pd
import yaml

try:
    from pyage.config.bootstrap import ensure_repo_imports
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pyage.config.bootstrap import ensure_repo_imports


ensure_repo_imports()


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
    selected_wells: list[str]
    calibration_tracers: list[str]
    tracer_scope: str
    date_round_decimals: int
    lpm_name: str
    launcher_enabled: bool


@dataclass
class PreparedHoltenCase:
    context: HoltenContext
    sampling_raw: pd.DataFrame
    observed_aggregated: pd.DataFrame
    observed_by_well: dict[str, pd.DataFrame]
    tracer_histories: dict[str, pd.DataFrame]
    preparation_log: pd.DataFrame


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid YAML structure in {path}")
    return payload


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def resolve_paths(config_path: Path | None = None) -> HoltenPaths:
    root = repo_root()
    example_dir = Path(__file__).resolve().parent
    yaml_path = config_path or (example_dir / "holten.yaml")
    data_dir = example_dir / "data"
    doc_dir = example_dir / "doc"
    generated_dir = example_dir / "generated"
    launcher_config_dir = generated_dir / "launcher_configs"
    tracer_source_dir = example_dir / "tracers"
    prepared_tracer_dir = example_dir / "prepared_tracers" / "data_tracer"
    lpm_data_dir = example_dir / "data_lpm"
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
        sampling_raw_path=doc_dir / "sampling_data.txt",
        tritium_raw_path=doc_dir / "local_tritium.txt",
        kr85_raw_path=doc_dir / "freiburg_krypton.txt",
        reference_results_path=doc_dir / "calibration_results.txt",
        aggregated_dataset_path=data_dir / "holten_2010_selected_wells.txt",
        benchmark_dir=benchmark_dir,
    )


def load_holten_config(config_path: Path | None = None) -> dict[str, Any]:
    paths = resolve_paths(config_path)
    return load_yaml(paths.yaml_path)


def build_context(config_path: Path | None = None) -> HoltenContext:
    paths = resolve_paths(config_path)
    cfg = load_holten_config(paths.yaml_path)
    holten_cfg = cfg.get("holten", {})
    campaign_cfg = holten_cfg.get("campaign", {})
    tracer_cfg = holten_cfg.get("tracers", {})
    prep_cfg = holten_cfg.get("preparation", {})
    launcher_cfg = holten_cfg.get("launcher", {})
    selected_wells = [str(w) for w in campaign_cfg.get("selected_wells", [])]
    calibration_tracers = [str(t) for t in tracer_cfg.get("calibration", [])]
    return HoltenContext(
        paths=paths,
        config=cfg,
        selected_wells=selected_wells,
        calibration_tracers=calibration_tracers,
        tracer_scope=str(campaign_cfg.get("tracer_scope", "holten_only")),
        date_round_decimals=int(prep_cfg.get("date_round_decimals", 5)),
        lpm_name=str(cfg.get("lpm", {}).get("model_name", "")),
        launcher_enabled=bool(launcher_cfg.get("enabled", False)),
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
