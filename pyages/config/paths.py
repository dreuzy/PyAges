# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical package-resource, repository, test-data, and result roots.

Workflow paths supplied in YAML are resolved by the workflow loaders rather
than by this module. Packaged core data use :mod:`importlib.resources`; the
result root comes from ``PYAGES_RESULTS_DIR`` or a user-level default.
"""

from __future__ import annotations

import os
from datetime import datetime
from importlib.resources import files
from pathlib import Path

# -------------------------------------------------------
# Root directories
# -------------------------------------------------------

# Root Directory of Repository
ROOT_DIRECTORY = Path(__file__).resolve().parents[2]

# Root Directory of Results (absolute via env, or user-level default)
_results_env = os.environ.get("PYAGES_RESULTS_DIR", "").strip()
if _results_env:
    ROOT_DIRECTORY_RESULTS = Path(_results_env)
else:
    ROOT_DIRECTORY_RESULTS = Path.home() / "results" / "PyAges"

# -------------------------------------------------------
# Sub-directories
# -------------------------------------------------------

# ``data_core`` is an explicit package in built distributions.  Resolving it
# through importlib.resources works both in a repository checkout and after a
# wheel installation, without assuming where site-packages is located.
_DATA_CORE_DIRECTORY = Path(str(files("data_core")))
DIRECTORY_TRACER_DATA = _DATA_CORE_DIRECTORY / "data_tracer"
DIRECTORY_LPM_DATA = _DATA_CORE_DIRECTORY / "data_lpm"


# -------------------------------------------------------
# Utility functions
# -------------------------------------------------------


def configuration_root(config_path: str | Path) -> Path:
    """Resolve checkout-relative configs while supporting standalone projects."""
    path = Path(config_path).resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "data_core"
        ).is_dir():
            return candidate
    current_directory = Path.cwd().resolve()
    if (current_directory / "pyproject.toml").is_file() and (
        current_directory / "data_core"
    ).is_dir():
        return current_directory
    return path.parent


def result_subdirectory(directory: str | Path, sub_directory: str) -> Path:
    """Create and return one named subdirectory below a results directory."""
    path = Path(directory) / sub_directory
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_path_component(value: str, *, label: str) -> str:
    """Return a user-derived path component after rejecting path traversal."""
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if (
        not value.strip()
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or ":" in value
        or "\0" in value
    ):
        raise ValueError(f"{label} must be a single non-empty path component")
    return value


def timestamp_name() -> str:
    """Return a timestamp string (year_month_day-hour_minute_second)."""
    now = datetime.now()
    return now.strftime("%Y_%m_%d-%H_%M_%S")


__all__ = [
    "DIRECTORY_LPM_DATA",
    "DIRECTORY_TRACER_DATA",
    "ROOT_DIRECTORY",
    "ROOT_DIRECTORY_RESULTS",
    "configuration_root",
    "result_subdirectory",
    "timestamp_name",
    "validate_path_component",
]
