# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Characterization tests for the installed single-date workflow."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyages.data_io.lpm_distribution import read_distribution
from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _headless_matplotlib_backend(monkeypatch) -> None:
    """Keep workflow tests independent of the optional notebook backend."""
    monkeypatch.setenv("MPLBACKEND", "Agg")


def _read_key_values(path: Path) -> dict[str, str]:
    """Read the canonical two-column metadata format used by calibrations."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def test_quickstart_writes_a_manifest_and_normalized_observations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "quickstart"
    monkeypatch.setattr(
        single_context, "dataset_results_directory", lambda _name, **_kwargs: output
    )
    monkeypatch.setattr(
        single_reporting,
        "export_concentration_chronicles",
        lambda *_args, **_kwargs: None,
    )

    result = single_date.run_single_date(
        Path("examples/templates/quickstart_single.yaml"),
        force_inline=True,
    )

    assert result == output
    assert (output / "concentrations.txt").is_file()
    observations = pd.read_table(output / "concentrations.txt")
    assert observations.columns.tolist() == [
        "element",
        "concentration",
        "error",
        "unit",
        "date",
    ]
    assert (observations["error"] > 0.0).all()
    manifest = json.loads((output / "result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert manifest["workflow"] == "single_date"
    assert manifest["status"] == "complete"
    assert manifest["configuration"]["path"].endswith("quickstart_single.yaml")
    assert "concentrations.txt" in manifest["artifacts_sha256"]
    assert manifest["details"]["dataset_year"] == 2010
    assert manifest["details"]["observation_error_policy"]["missing_error_rel"] == 0.01
    assert manifest["details"]["observation_error_policy"]["transformations"]
    assert any(item["path"].endswith("params.yaml") for item in manifest["inputs"])


def test_quickstart_exercised_here_is_the_documented_tutorial_command() -> None:
    tutorial = (ROOT / "docs" / "user-guide" / "tutorial.md").read_text(
        encoding="utf-8"
    )

    assert "pyages run examples/templates/quickstart_single.yaml" in tutorial
    assert '`"status": "complete"`' not in tutorial
    assert '"status": "complete"' in tutorial


def test_objective_only_run_uses_resolved_errors_without_calibration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_config = ROOT / "examples" / "templates" / "quickstart_single.yaml"
    payload = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    payload["dataset"]["data_dir"] = str(
        ROOT / "examples" / "natural" / "ploemeur" / "data"
    )
    payload["lpm"]["data_directory"] = str(ROOT / "data_core" / "data_lpm")
    payload["run"]["objective_function"] = True
    payload["objective_function"]["nmodels"] = 4
    config = tmp_path / "objective_only.yaml"
    config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    output = tmp_path / "objective_only"
    monkeypatch.setattr(
        single_context, "dataset_results_directory", lambda _name, **_kwargs: output
    )
    monkeypatch.setattr(
        single_reporting,
        "export_concentration_chronicles",
        lambda *_args, **_kwargs: None,
    )
    result = single_date.run_single_date(config, force_inline=True)

    assert result == output
    assert (output / "objective_function_grid.txt").is_file()
    observations = pd.read_table(output / "concentrations.txt")
    assert (observations["error"] > 0.0).all()


def test_multichain_smoke_runs_end_to_end_from_its_versioned_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Exercise the installed workflow through the versioned wheel-smoke YAML."""
    config = ROOT / "examples" / "templates" / "smoke_multichain.yaml"
    output = tmp_path / "ploemeur_multichain"
    monkeypatch.setattr(
        single_context,
        "dataset_results_directory",
        lambda _name, **_kwargs: output,
    )
    monkeypatch.setattr(
        single_reporting,
        "export_concentration_chronicles",
        lambda *_args, **_kwargs: None,
    )
    result = single_date.run_single_date(config, force_inline=False)

    assert result == output
    mh_directory = output / "Metropolis_Hastings"
    chain_frames = [
        read_distribution(
            mh_directory
            / "chains"
            / f"chain_{chain_id:03d}"
            / "lpm_dist_calibrated.txt"
        )
        for chain_id in (1, 2)
    ]
    assert [len(frame) for frame in chain_frames] == [10, 10]
    assert all({"mu", "shift"}.issubset(frame.columns) for frame in chain_frames)
    pooled = read_distribution(mh_directory / "lpm_dist_calibrated.txt")
    assert len(pooled) == 20

    covariance = pd.read_table(
        mh_directory / "proposal_covariance.tsv",
        index_col=0,
    )
    assert covariance.index.tolist() == ["mu", "shift"]
    assert covariance.columns.tolist() == ["mu", "shift"]
    assert np.all(np.linalg.eigvalsh(covariance.to_numpy(dtype=float)) > 0.0)
    assert len(pd.read_table(mh_directory / "pilot" / "chain_001_samples.tsv")) == 29

    diagnostics = pd.read_table(mh_directory / "mcmc_diagnostics.tsv")
    assert {"parameter", "rhat", "bulk_ess", "tail_ess", "mcse_mean"}.issubset(
        diagnostics.columns
    )
    assert {"mu", "shift"}.issubset(set(diagnostics["parameter"]))
    parameters = _read_key_values(mh_directory / "parameters_calibration.txt")
    run_results = _read_key_values(mh_directory / "results_calibration.txt")
    provenance = _read_key_values(mh_directory / "ensemble_provenance.txt")
    assert parameters["execution_mode"] == "multi_chain"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"
    assert parameters["retained_sample_count_per_chain"] == "10"
    assert run_results["qualification_status"] == "not_qualified"
    assert run_results["pooling_written"] == "True"
    assert provenance["master_seed"] == "20260831"
    assert provenance["production_seed_001"] != provenance["production_seed_002"]

    manifest = json.loads((output / "result_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["details"]["calibrations"] == ["Metropolis_Hastings"]
    assert (
        "Metropolis_Hastings/chains/chain_001/lpm_dist_calibrated.txt"
        in manifest["artifacts_sha256"]
    )
