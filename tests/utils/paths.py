"""Path helpers for tests."""

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def lpm_dir() -> Path:
    return repo_root() / "sources" / "LPM"


def lpm_data_dir() -> Path:
    return repo_root() / "sources" / "LPM_data"
