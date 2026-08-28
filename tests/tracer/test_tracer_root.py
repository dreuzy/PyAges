# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
tests/tracer/test_tracer_root.py (or test_tracer_concentration.py)

Pytest test file for the Tracer class.

This file illustrates three useful levels of testing in scientific computing:

1) Consistency tests / smoke tests
   - The code initializes
   - Properties are defined
   - Outputs are finite numbers (not NaN or infinity)

2) Tests of expected behavior for unsupported usage
   - Check that an exception is raised (for example, ValueError)

3) Golden test (reference value / non-regression)
   - Compare a computed value with a reference value stored in a JSON file
   - The pytest --update-golden option recomputes and updates reference values

Prerequisites:
- A conftest.py at the repository root (C:\\codes\\pyages\\conftest.py) that defines:
  - the --update-golden option
  - the update_golden and golden_store fixtures
  - the save_golden_store(store) function
- A golden reference file:
  tests/golden/tracer_values.json
"""

import math
from pathlib import Path

import pytest

# Fixture-owned facade that preserves pytest options and the canonical golden path.
from conftest import save_golden_store

# Import the code under test after the golden-value facade.
from pyages.tracer.tracer_root import Tracer

# ---------------------------------------------------------------------------
# Utility: locate test data
# ---------------------------------------------------------------------------


def _data_tracer_dir() -> Path:
    """
    Return the path to the directory containing the data required by the tests.

    Expected directory structure (example):
      <repo_root>/
        conftest.py
        pyages/
          ...
        data_core/
          data_tracer/
        tests/
          tracer/
            test_tracer_root.py

    __file__ = path to the current test file.
    parents[2] moves up from:
      - parents[0]: file directory (for example, tests/tracer)
      - parents[1]: tests
      - parents[2]: repository root

    Then construct: <repo_root>/data_core/data_tracer
    """
    return Path(__file__).resolve().parents[2] / "data_core" / "data_tracer"


def _tracer_names(exclude=None) -> list[str]:
    """
    List the available tracers (subdirectories with YAML), excluding selected ones.
    """
    tracer_dir = _data_tracer_dir()
    exclude_set = set(exclude or [])
    names = []
    for item in tracer_dir.iterdir():
        if not item.is_dir():
            continue
        yaml_file = item / f"{item.name}.yaml"
        if yaml_file.exists() and item.name not in exclude_set:
            names.append(item.name)
    return sorted(names)


# ---------------------------------------------------------------------------
# Consistency tests (smoke tests)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tracer_name", _tracer_names(exclude=["NO3"]))
def test_tracer_smoke_all(tracer_name):
    """
    Run a minimal smoke test for all tracers except NO3.
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name=tracer_name)

    assert tracer.name == tracer_name
    assert tracer.unit != ""
    assert tracer.datemin < tracer.datemax

    value = tracer.get_concentration(date=2000.0, time=10.0)
    assert math.isfinite(float(value))

    try:
        max_val = tracer.max_value()
        assert math.isfinite(max_val)
    except ValueError:
        pass


def test_tracer_chronicle_cfc11_basics():
    """
    Run a smoke test on a chronicle-based tracer (for example, cfc11).

    Objectives:
    - Check that the Tracer object initializes correctly
    - Check that key attributes are consistent
    - Check that the main methods return finite numeric values

    This test does NOT guarantee detailed scientific validity; it primarily checks
    that the code works and that its outputs are reasonable.
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name="cfc11")

    # --- Basic attributes ---
    assert tracer.name == "cfc11"

    # The unit should be set; otherwise, the data or properties are incomplete.
    assert tracer.unit != ""

    # The date range must be consistent.
    assert tracer.datemin < tracer.datemax

    # --- Numeric outputs must be finite ---
    # Force float(value) because get_concentration may return a NumPy scalar.
    value = tracer.get_concentration(date=2010.0, time=20.0)
    assert math.isfinite(float(value))

    # Mean value (over one year, for example).
    mean_val = tracer.mean_value(2010.0)
    assert math.isfinite(mean_val)

    # Global maximum value.
    max_val = tracer.max_value()
    assert math.isfinite(max_val)

    # Domain assumption: the concentration should not be negative.
    # Adjust this if negative values are possible in the model.
    assert max_val >= 0


def test_tracer_constant_recharge_so4():
    """
    Run a smoke test and exception test on a constant-recharge tracer (SO4).

    Objectives:
    - get_concentration must work and return a finite value
    - max_value may not be defined for this type, so check that it raises ValueError
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name="SO4")

    value = tracer.get_concentration(date=2000.0, time=10.0)
    assert math.isfinite(float(value))

    # Test expected error behavior here: max_value() is not meaningful for this
    # tracer, so it should raise an exception.
    with pytest.raises(ValueError):
        tracer.max_value()


def test_tracer_allows_metadata_block(tmp_path):
    tracer_dir = tmp_path / "data_tracer"
    tracer_name = "meta_tracer"
    tracer_path = tracer_dir / tracer_name
    tracer_path.mkdir(parents=True)
    (tracer_path / f"{tracer_name}.yaml").write_text(
        "\n".join(
            [
                "unit: TU",
                "recharge_constant: 1.0",
                "half_life: 12.32",
                "datemin: 1950.0",
                "datemax: 2021.0",
                "metadata:",
                "  reference: local test",
                "  notes: keep for example workflows",
                "",
            ]
        ),
        encoding="utf-8",
    )

    tracer = Tracer(tracer_dir, name=tracer_name)

    assert tracer.unit == "TU"
    assert tracer.datemin == 1950.0
    assert tracer.datemax == 2021.0


# ---------------------------------------------------------------------------
# Golden test (reference value / non-regression)
# ---------------------------------------------------------------------------


def _golden_key(tracer_name: str, date: float, time: float) -> str:
    """
    Build a stable key for indexing a reference value in the JSON file.

    Example:
      "cfc11:date=2001.0,time=25.0"

    The goal is to avoid ambiguity and provide a stable, copyable key.
    """
    return f"{tracer_name}:date={date},time={time}"


@pytest.mark.parametrize("tracer_name", _tracer_names(exclude=["NO3"]))
def test_tracer_get_concentration_golden(tracer_name, update_golden, golden_store):
    """
    Run a golden test for get_concentration at a specific point (date, time).

    Two modes:

    - Normal mode (without an option):
        Compare the computed value with the reference value stored under a
        stable key in tests/golden/tracer_values.json.

    - Update mode (with --update-golden):
        Recompute the value, write it to the JSON file, and then skip the test
        without comparing values.

    Why skip in update mode?
      - To make the intent explicit: "I am updating the reference."
      - To avoid mixing updates and validation in the same run.
    """
    tracer_dir = _data_tracer_dir()
    tracer = Tracer(tracer_dir, name=tracer_name)

    # Test-point parameters must be stable and reproducible.
    date = 0.5 * (tracer.datemin + tracer.datemax)
    time = min(10.0, max(0.0, date - tracer.datemin))

    # Computed value.
    value = float(tracer.get_concentration(date=date, time=time))

    # Storage and retrieval key in the golden store.
    key = _golden_key(tracer_name, date, time)

    # Print a copyable value for inspection in the console.
    # This is useful for debugging or manual validation.
    print(f"[golden] {key} = {value:.12e}")

    if update_golden:
        # --- Update mode ---
        golden_store[key] = value
        save_golden_store(golden_store)

        # Do not validate here; only report that the reference was updated.
        pytest.skip(f"Golden updated: {key} = {value:.12e}")
    else:
        # --- Comparison mode ---
        # If the reference does not exist yet, require the user to generate it
        # instead of allowing the test to pass without checking anything.
        if key not in golden_store:
            pytest.fail(
                f"Golden value missing for {key}. Run: pytest -s --update-golden"
            )

        expected = float(golden_store[key])

        # Floating-point comparison with tolerances.
        # rel = relative tolerance; abs = absolute tolerance.
        print(
            f"[golden] comparing {key}: computed={value:.12e} expected={expected:.12e}"
        )
        assert value == pytest.approx(expected, rel=1e-6, abs=1e-6)
