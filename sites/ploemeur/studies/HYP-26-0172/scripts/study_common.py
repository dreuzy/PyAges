"""Shared helpers for the HYP-26-0172 experiment matrix."""

from __future__ import annotations

import csv
import hashlib
import json
import re
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
PROFILE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,15}")


def split_field(value: str) -> list[str]:
    return [item.strip() for item in value.split("+") if item.strip()]


def validate_profile(value: str) -> str:
    """Return a filesystem-safe campaign profile name."""
    if not PROFILE_PATTERN.fullmatch(value):
        raise ValueError(
            "profile must contain 1-16 lowercase letters, digits, underscores, "
            "or hyphens"
        )
    return value


def profile_results_root(profile: str) -> Path:
    """Return the isolated results root for a campaign profile."""
    validate_profile(profile)
    return RESULTS_ROOT if profile == "production" else RESULTS_ROOT / profile


def profiled_experiment_id(experiment_id: str, profile: str) -> str:
    """Return the run identifier used within a campaign profile."""
    validate_profile(profile)
    return experiment_id


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
    tracer_root = REPO_ROOT / "data_core" / "data_tracer"
    yield from sorted(path for path in tracer_root.rglob("*") if path.is_file())
    lpm_root = REPO_ROOT / "sites" / "ploemeur" / "params_lpm"
    for model in split_field(row["lpm_models"]):
        yield lpm_root / model / "params.yaml"
    ori = REPO_ROOT / "sites" / "ploemeur" / "data" / "ori"
    for well in split_field(row["wells"]):
        for path in sorted(ori.glob(f"ori_ploemeur_{well}_*.txt")):
            yield path


def source_files() -> Iterable[Path]:
    """Yield source files that define the numerical workflow."""
    yield REPO_ROOT / "pyproject.toml"
    for relative_root in ("pyage", "scripts", "sites/ploemeur"):
        root = REPO_ROOT / relative_root
        yield from sorted(root.rglob("*.py"))


def checksums(paths: Iterable[Path]) -> dict[str, str]:
    """Return stable repository-relative SHA-256 checksums."""
    return {
        str(path.relative_to(REPO_ROOT)): sha256(path)
        for path in paths
        if path.is_file()
    }


def checksums_digest(values: dict[str, str]) -> str:
    """Hash a checksum mapping into one compact campaign fingerprint."""
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
