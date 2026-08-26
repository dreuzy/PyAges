"""Contracts for versioned public workflow result metadata."""

import hashlib
import json

from pyage import __version__
from pyage.workflows.result_manifest import (
    RESULT_SCHEMA_VERSION,
    write_result_manifest,
)


def test_result_manifest_is_versioned_and_deterministic(tmp_path) -> None:
    config = tmp_path / "case.yaml"
    config.write_text("model: exp\n", encoding="utf-8")
    artifact = tmp_path / "samples.csv"
    artifact.write_text("mu\n10\n", encoding="utf-8")
    target = write_result_manifest(
        tmp_path,
        workflow="single_date",
        config_path=config,
        input_paths=[config],
        details={"lpm": "exp"},
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RESULT_SCHEMA_VERSION == 2
    assert payload["status"] == "complete"
    assert payload["workflow"] == "single_date"
    assert payload["pyage_version"] == __version__
    assert payload["details"] == {"lpm": "exp"}
    assert (
        payload["configuration"]["sha256"]
        == hashlib.sha256(config.read_bytes()).hexdigest()
    )
    assert payload["inputs"][0]["sha256"] == payload["configuration"]["sha256"]
    assert payload["artifacts_sha256"] == {
        "case.yaml": hashlib.sha256(config.read_bytes()).hexdigest(),
        "samples.csv": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
    assert payload["environment"]["dependencies"]["numpy"]
    assert "tracked_workspace_sha256" in payload["repository"]
