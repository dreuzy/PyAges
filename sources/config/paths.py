# -*- coding: utf-8 -*-
"""
Paths configuration for PyAge.

All paths are resolved relative to the repository root, except the results
directory, which is set via environment variable or a user-level default.
"""

from datetime import datetime
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

ROOT_DIRECTORY_RESULTS.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------
# Sub-directories
# -------------------------------------------------------

DIRECTORY_TRACER_DATA = ROOT_DIRECTORY / "core_data" / "tracer_data"
DIRECTORY_TEST = ROOT_DIRECTORY_SRC / "tests_data"
DIRECTORY_LPM_DATA = ROOT_DIRECTORY / "core_data" / "LPM_data"


# -------------------------------------------------------
# Utility functions
# -------------------------------------------------------

def results_directory(directory, sub_directory):
    """Create sub-directory if necessary and return its path."""
    path = Path(directory) / sub_directory
    path.mkdir(parents=True, exist_ok=True)
    return path


def name_dhms():
    """Return a timestamp string (year_month_day-hour_minute_second)."""
    now = datetime.now()
    return now.strftime("%Y_%m_%d-%H_%M_%S")


