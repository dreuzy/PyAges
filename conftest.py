# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import json
import sys
from pathlib import Path

import pytest

from tests.utils import golden as golden_utils

# ---------------------------------------------------------------------------
# 1) Locate the project and add "pyages/" to the test PYTHONPATH
# ---------------------------------------------------------------------------

# REPO_ROOT = directory containing this conftest.py file (usually the repository root)
REPO_ROOT = Path(__file__).resolve().parent

# Repository root directory (used to import pyages.*)
SRC_DIR = REPO_ROOT

# sys.path = list of directories where Python looks for modules to import.
# Add the repository root here so that project imports (pyages.*) work even if
# the project is not installed as a package (pip install -e .).
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# 2) Location of the golden reference file
# ---------------------------------------------------------------------------

# JSON file that stores the golden reference values.
# Example content:
# {
#   "cfc11:date=2001.0,time=25.0": 0.002347891234
# }
GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "tracer_values.json"


# ---------------------------------------------------------------------------
# 3) Add a pytest command-line option
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    """
    Pytest hook used to add options to the `pytest ...` command.

    This adds:
      --update-golden

    Usage:
      pytest --update-golden
    """
    parser.addoption(
        "--update-golden",
        action="store_true",  # Boolean option: present => True, absent => False
        default=False,
        help="Update golden reference values instead of asserting.",
    )
    parser.addoption(
        "--run-extensive",
        action="store_true",
        default=False,
        help="Run extensive/slow tests (opt-in).",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "extensive: marks tests as extensive/slow (run with --run-extensive)",
    )


# ---------------------------------------------------------------------------
# 4) Fixtures: access options and golden data in tests
# ---------------------------------------------------------------------------


@pytest.fixture
def update_golden(request) -> bool:
    """
    Pytest fixture that exposes the update_golden Boolean to tests.

    In a test:
      def test_x(update_golden):
          if update_golden:
              ... # update mode
          else:
              ... # comparison mode
    """
    return bool(request.config.getoption("--update-golden"))


def pytest_collection_modifyitems(config, items):
    """Skip extensive tests unless explicitly enabled."""
    if config.getoption("--run-extensive"):
        return
    skip_extensive = pytest.mark.skip(reason="needs --run-extensive to run")
    for item in items:
        if "extensive" in item.keywords:
            item.add_marker(skip_extensive)


@pytest.fixture
def golden_store() -> dict:
    """
    Pytest fixture that loads the golden-value JSON file at the start of a test.

    - Creates the tests/golden/ directory if it does not exist
    - Returns {} if the JSON file does not exist
    - Raises a pytest "UsageError" if the JSON is invalid (a corrupted file or
      an invalid manual edit), providing a clear message and stopping the run
    """
    # Ensure that the directory exists, even if it is empty.
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # No file means no reference values, so return an empty dictionary.
    if not GOLDEN_PATH.exists():
        return {}

    # If the file exists, attempt to parse it as JSON.
    try:
        return golden_utils.load_golden(GOLDEN_PATH)
    except json.JSONDecodeError as e:
        # UsageError reports a configuration/usage issue more clearly than a raw traceback.
        raise pytest.UsageError(
            f"Golden file is not valid JSON: {GOLDEN_PATH}\n{e}"
        ) from e


# ---------------------------------------------------------------------------
# 5) Utility function: save golden values safely
# ---------------------------------------------------------------------------


def save_golden_store(store: dict) -> None:
    """
    Write the `store` dictionary to GOLDEN_PATH.

    Write it atomically:
      1) first write to a temporary *.tmp file
      2) then replace the final file

    This prevents a partially written or corrupted tracer_values.json file if
    the process is interrupted during the write.
    """
    golden_utils.save_golden(GOLDEN_PATH, store)
