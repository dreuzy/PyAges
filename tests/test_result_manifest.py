"""Contracts for versioned public workflow result metadata."""

import json

from pyage import __version__
from pyage.workflows.result_manifest import (
    RESULT_SCHEMA_VERSION,
    write_result_manifest,
)


def test_result_manifest_is_versioned_and_deterministic(tmp_path) -> None:
    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_name="case.yaml",
        details={"lpm": "exp"},
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {
        "config_name": "case.yaml",
        "details": {"lpm": "exp"},
        "pyage_version": __version__,
        "schema_version": RESULT_SCHEMA_VERSION,
        "workflow": "single_date",
    }
