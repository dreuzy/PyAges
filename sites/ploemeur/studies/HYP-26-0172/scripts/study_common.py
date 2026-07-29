"""Shared helpers for the HYP-26-0172 experiment matrix."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[5]
STUDY_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = STUDY_ROOT / "experiment_matrix.csv"
RESULTS_ROOT = REPO_ROOT / "results" / "HYP-26-0172"
REQUIRED_COLUMNS = {
    "experiment_id",
    "enabled",
    "family",
    "wells",
    "tracers",
    "lpm_models",
    "prior_pipeline",
    "relative_errors",
    "seeds",
    "params_path",
    "article_outputs",
    "notes",
}


def split_field(value: str) -> list[str]:
    return [item.strip() for item in value.split("+") if item.strip()]


def load_matrix(path: Path = MATRIX_PATH) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Matrix has no header: {path}")
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"Matrix is missing columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_files(row: dict[str, str], params_path: Path) -> Iterable[Path]:
    yield MATRIX_PATH
    yield params_path
    for relative in (
        "sites/ploemeur/params/ploemeur_observations.yaml",
        "sites/ploemeur/params/prior_pipeline_presets.yaml",
    ):
        yield REPO_ROOT / relative
    ori = REPO_ROOT / "sites" / "ploemeur" / "data" / "ori"
    for well in split_field(row["wells"]):
        for path in sorted(ori.glob(f"ori_ploemeur_{well}_*.txt")):
            yield path


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
