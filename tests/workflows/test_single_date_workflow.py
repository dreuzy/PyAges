"""Characterization tests for the installed single-date workflow."""

from __future__ import annotations

import json
from pathlib import Path

from pyage.workflows import single_date


def test_quickstart_writes_a_manifest_and_normalized_observations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "quickstart"
    monkeypatch.setattr(single_date, "dataset_results_directory", lambda _name: output)
    monkeypatch.setattr(
        single_date.concentrations_time,
        "display_concentration_times",
        lambda *_args, **_kwargs: None,
    )

    result = single_date.run_single_date(
        Path("examples/templates/quickstart_single.yaml"),
        force_inline=True,
    )

    assert result == output
    assert (output / "concentrations.txt").is_file()
    manifest = json.loads((output / "result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["workflow"] == "single_date"
    assert manifest["status"] == "complete"
    assert manifest["configuration"]["path"].endswith("quickstart_single.yaml")
    assert "concentrations.txt" in manifest["artifacts_sha256"]
