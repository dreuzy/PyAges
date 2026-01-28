"""Path helpers for tests."""

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def lpm_dir() -> Path:
    return repo_root() / "sources" / "LPM" / "models"


def lpm_data_dir() -> Path:
    return repo_root() / "data_core" / "data_LPM"


def tracer_data_dir() -> Path:
    return repo_root() / "data_core" / "data_tracer"
