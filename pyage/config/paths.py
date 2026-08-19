# -*- coding: utf-8 -*-
"""
Paths configuration for PyAge.

All paths are resolved relative to the repository root, except the results
directory, which is set via environment variable or a user-level default.
"""

from datetime import datetime
from importlib.resources import files
from pathlib import Path
import os


# -------------------------------------------------------
# Root directories
# -------------------------------------------------------

# Root Directory of Application (resolved from this file location)
ROOT_DIRECTORY_SRC = Path(__file__).resolve().parents[1]

# Root Directory of Repository
ROOT_DIRECTORY = ROOT_DIRECTORY_SRC.parent

# Root Directory of Results (absolute via env, or user-level default)
_results_env = os.environ.get("PYAGE_RESULTS_DIR", "").strip()
if _results_env:
    ROOT_DIRECTORY_RESULTS = Path(_results_env)
else:
    ROOT_DIRECTORY_RESULTS = Path.home() / "results" / "PyAge"

# -------------------------------------------------------
# Sub-directories
# -------------------------------------------------------

# ``data_core`` is an explicit package in built distributions.  Resolving it
# through importlib.resources works both in a repository checkout and after a
# wheel installation, without assuming where site-packages is located.
_DATA_CORE_DIRECTORY = Path(str(files("data_core")))
DIRECTORY_TRACER_DATA = _DATA_CORE_DIRECTORY / "data_tracer"
DIRECTORY_TEST = ROOT_DIRECTORY / "tests" / "data"
DIRECTORY_LPM_DATA = _DATA_CORE_DIRECTORY / "data_lpm"


# -------------------------------------------------------
# Utility functions
# -------------------------------------------------------

def result_subdirectory(directory: str | Path, sub_directory: str) -> Path:
    """Create and return one named subdirectory below a results directory."""
    path = Path(directory) / sub_directory
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp_name() -> str:
    """Return a timestamp string (year_month_day-hour_minute_second)."""
    now = datetime.now()
    return now.strftime("%Y_%m_%d-%H_%M_%S")


__all__ = [
    "DIRECTORY_LPM_DATA",
    "DIRECTORY_TEST",
    "DIRECTORY_TRACER_DATA",
    "ROOT_DIRECTORY",
    "ROOT_DIRECTORY_RESULTS",
    "ROOT_DIRECTORY_SRC",
    "result_subdirectory",
    "timestamp_name",
]


