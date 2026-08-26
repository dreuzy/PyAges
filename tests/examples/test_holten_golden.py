from __future__ import annotations

from pathlib import Path

from tests.examples.holten_test_support import (
    assert_nested_close,
    build_local_4bin_mh_record,
    build_local_4bin_record,
    build_prepare_record,
    build_reference_comparison_record,
)
from tests.utils import golden as golden_utils

pytest_plugins = ("tests.examples.holten_fixtures",)


GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "golden"
    / "holten_example_values.json"
)


def test_holten_golden(
    update_golden,
    prepared_holten_case,
    local_4bin_outputs,
    local_4bin_mh_outputs,
    reference_comparison,
):
    record = {
        "prepare": build_prepare_record(prepared_holten_case),
        "local_4bin": build_local_4bin_record(local_4bin_outputs),
        "local_4bin_mh_nstep_600_seed_12345": build_local_4bin_mh_record(
            local_4bin_mh_outputs
        ),
        "reference_comparison": build_reference_comparison_record(reference_comparison),
    }

    store = golden_utils.load_golden(GOLDEN_PATH)
    key = "holten_default_case"

    if update_golden:
        store[key] = record
        golden_utils.save_golden(GOLDEN_PATH, store)
        return

    assert key in store, f"Missing golden entry for {key}. Run with --update-golden."
    # Optimizer results can drift slightly across the supported SciPy releases.
    assert_nested_close(record, store[key], tol=5e-4, atol=5e-6)
