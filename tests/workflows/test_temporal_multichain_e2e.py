# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""True end-to-end coverage of multi-chain MH in the temporal workflow."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pyages.data_io.lpm_distribution import read_distribution
from pyages.workflows.temporal import run_temporal

ROOT = Path(__file__).resolve().parents[2]


def test_temporal_workflow_runs_real_pilot_chains_diagnostics_and_pooling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Exercise the installed temporal path without mocking any MH component."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    results_root = tmp_path / "results"
    payload = {
        "dataset": {
            "file": str(
                ROOT
                / "examples"
                / "natural"
                / "ploemeur_temporal"
                / "data"
                / "ori_ploemeur_F09_2005_2024.txt"
            ),
            "error_rel": 0.2,
            "missing_error_rel": 0.01,
        },
        "lpm_models": {
            "list": ["exp_shifted"],
            "directory": str(ROOT / "data_core" / "data_lpm"),
        },
        "workflow": {"mode": "span"},
        "calibration": {
            "explo_res": 2,
            "mh_nsteps": 120,
            "burn_in": 0.1,
            "nskip": 10,
            "lpm_number": 0,
            "seed_enabled": False,
            "multichain": {
                "enabled": True,
                "chains": 2,
                "master_seed": 20260831,
                "initialization": {"strategy": "bounds_stratified"},
                "pilot": {
                    "enabled": True,
                    "nstep": 40,
                    "burn_in": 0.25,
                    "covariance_mode": "pooled_within_chain",
                    "relative_ridge": 1.0e-6,
                    "proposal_multiplier": "auto",
                    "save_samples": True,
                },
                "diagnostics": {
                    "max_rhat": 1.01,
                    "min_bulk_ess": 300,
                    "min_tail_ess": 300,
                    # Ten retained draws per chain test integration, not
                    # scientific convergence.
                    "require_convergence": False,
                },
            },
        },
        "figures": {
            "temporal": False,
            "distributions": False,
            "concentrations_2d": False,
        },
        "results": {
            "use_default": False,
            "directory": str(results_root),
            "study_name": "temporal_multichain_e2e",
        },
    }
    config = tmp_path / "temporal_multichain.yaml"
    config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    case_directory = run_temporal(config)

    method_directory = case_directory / "exp_shifted"
    chain_directories = sorted((method_directory / "chains").glob("chain_*"))
    assert [directory.name for directory in chain_directories] == [
        "chain_001",
        "chain_002",
    ]
    chains = [
        read_distribution(directory / "lpm_dist_calibrated.txt")
        for directory in chain_directories
    ]
    assert [len(chain) for chain in chains] == [10, 10]
    pooled = read_distribution(method_directory / "lpm_dist_calibrated.txt")
    assert len(pooled) == 20

    covariance = pd.read_table(
        method_directory / "proposal_covariance.tsv",
        index_col=0,
    ).to_numpy(dtype=float)
    assert covariance.shape == (2, 2)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)
    assert (method_directory / "pilot" / "chain_001_samples.tsv").is_file()
    assert (method_directory / "mcmc_diagnostics.tsv").is_file()

    mode_directory = case_directory.parent
    manifest = json.loads(
        (mode_directory / "result_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["details"]["lpms"] == ["exp_shifted"]
    assert (
        "span_full/exp_shifted/ensemble_provenance.txt" in manifest["artifacts_sha256"]
    )
