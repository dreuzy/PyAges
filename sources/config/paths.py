# -*- coding: utf-8 -*-
"""
Paths configuration for PyAge.
"""

from datetime import datetime
from pathlib import Path


# -------------------------------------------------------
# Root directories
# -------------------------------------------------------

# Root Directory of Results
ROOT_DIRECTORY_RESULTS = next(
    (p for p in [Path("D:/results/PyAge"), Path("C:/results/PyAge")] if p.exists()),
    None
)

# Root Directory of Application
ROOT_DIRECTORY_SRC = next(
    (p for p in [Path("D:/codes/pyage/sources"), Path("C:/codes/pyage/sources")] if p.exists()),
    None
)

# Root Directory of Repository
ROOT_DIRECTORY = ROOT_DIRECTORY_SRC.parent if ROOT_DIRECTORY_SRC else None

if ROOT_DIRECTORY_RESULTS is None:
    raise FileNotFoundError("No ROOT_DIRECTORY_RESULTS found")
if ROOT_DIRECTORY_SRC is None:
    raise FileNotFoundError("No ROOT_DIRECTORY_SRC found")
if ROOT_DIRECTORY is None:
    raise FileNotFoundError("No ROOT_DIRECTORY found")

# -------------------------------------------------------
# Sub-directories
# -------------------------------------------------------

DIRECTORY_TRACER_DATA = ROOT_DIRECTORY / "core_data" / "tracer_data"
DIRECTORY_TEST = ROOT_DIRECTORY_SRC / "tests_data"
directory_lpm_data = ROOT_DIRECTORY / "core_data" / "LPM_data"


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


def results_directory_dhms(sub_directory, directory=ROOT_DIRECTORY_RESULTS):
    """Create dated sub-directory under directory/sub_directory."""
    base = results_directory(directory, sub_directory)
    return results_directory(base, sub_directory)
