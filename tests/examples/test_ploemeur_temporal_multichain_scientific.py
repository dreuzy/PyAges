# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Extensive multi-chain qualification of the temporal Ploemeur profile.

The field record has no known parameter truth.  This test therefore qualifies
the canonical temporal workflow, convergence, joint-row integrity, prior and
proposal provenance, and in-sample coherence over the complete observation
span.  It does not establish out-of-sample skill or LPM uniqueness.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyages.calibration.problem import CalibrationProblem, resolve_observation_errors
from pyages.concentrations import Concentrations
from pyages.config.models import TemporalParams
from pyages.data_io.lpm_distribution import read_distribution
from pyages.workflows.temporal import run_temporal

ROOT = Path(__file__).resolve().parents[2]
TEACHING_CONFIG = (
    ROOT / "examples" / "natural" / "ploemeur_temporal" / "ploemeur_temporal.yaml"
)
MULTICHAIN_CONFIG = (
    ROOT
    / "examples"
    / "natural"
    / "ploemeur_temporal"
    / "ploemeur_temporal_multichain.yaml"
)
DATA = (
    ROOT
    / "examples"
    / "natural"
    / "ploemeur_temporal"
    / "data"
    / "ori_ploemeur_F09_2005_2024.txt"
)
LPM_DIRECTORY = ROOT / "data_core" / "data_lpm"

CHAIN_COUNT = 4
PRODUCTION_STEPS = 5_000
BURN_IN = 0.20
RETAINED_PER_CHAIN = PRODUCTION_STEPS - math.floor(BURN_IN * PRODUCTION_STEPS) - 1
MAX_RHAT = 1.01
MIN_ESS = 300.0
MAX_RELATIVE_MCSE = 0.10
MIN_ACCEPTANCE_RATE = 0.20
MAX_ACCEPTANCE_RATE = 0.50
EXPECTED_PRIORS = {
    "mu": {"type": "normal", "mean": 25.0, "std": 5.0, "unit": "year"},
    "shift": {"type": "normal", "mean": 10.0, "std": 2.0, "unit": "year"},
}
DIAGNOSTIC_NAMES = (
    "mu",
    "shift",
    "mean",
    "std",
    "p10",
    "p25",
    "p50",
    "p75",
    "p90",
)


def _read_key_values(path: Path) -> dict[str, str]:
    """Read the canonical two-column calibration metadata format."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _scientific_payload(results_root: Path) -> dict:
    """Load and relocate the maintained temporal qualification profile."""
    teaching = yaml.safe_load(TEACHING_CONFIG.read_text(encoding="utf-8"))
    assert "multichain" not in teaching["calibration"]
    payload = yaml.safe_load(MULTICHAIN_CONFIG.read_text(encoding="utf-8"))
    payload["dataset"]["file"] = str(DATA)
    payload["lpm_models"]["directory"] = str(LPM_DIRECTORY)
    payload["results"] = {
        "use_default": False,
        "directory": str(results_root),
        "study_name": "ploemeur_temporal_multichain",
    }
    calibration = payload["calibration"]
    multichain = calibration["multichain"]
    assert payload["dataset"]["error_rel"] == 0.20
    assert payload["dataset"]["missing_error_rel"] == 0.01
    assert payload["lpm_models"]["list"] == ["exp_shifted"]
    assert payload["workflow"]["mode"] == "span"
    assert payload["results"]["study_name"] == "ploemeur_temporal_multichain"
    assert (
        calibration["mh_nsteps"],
        calibration["burn_in"],
        calibration["nskip"],
    ) == (PRODUCTION_STEPS, BURN_IN, 1)
    assert (multichain["chains"], multichain["master_seed"]) == (
        CHAIN_COUNT,
        20260831,
    )
    assert multichain["initialization"] == {
        "strategy": "bounds_stratified",
        "max_attempts": 100,
    }
    assert multichain["pilot"] == {
        "enabled": True,
        "nstep": 2_000,
        "burn_in": 0.50,
        "covariance_mode": "pooled_within_chain",
        "relative_ridge": 1.0e-6,
        "proposal_multiplier": "auto",
        "save_samples": False,
    }
    assert multichain["diagnostics"] == {
        "max_rhat": MAX_RHAT,
        "min_bulk_ess": MIN_ESS,
        "min_tail_ess": MIN_ESS,
        "require_convergence": True,
    }
    return payload


def test_ploemeur_temporal_multichain_profile_contract(tmp_path: Path) -> None:
    """Validate the maintained profile and its field/prior inputs quickly."""
    payload = _scientific_payload(tmp_path / "unused-results")
    params = TemporalParams.model_validate(payload)

    assert params.workflow.mode == "span"
    assert params.calibration.multichain is not None
    assert params.calibration.multichain.enabled
    observations = Concentrations.from_file(DATA)
    assert len(observations.frame) == 58
    assert observations.frame["date"].nunique() == 20
    assert observations.frame["error"].eq(0.0).all()
    assert observations.frame["concentration"].ne(0.0).all()
    assert observations.frame.groupby("element").size().to_dict() == {
        "cfc11": 18,
        "cfc12": 20,
        "cfc113": 20,
    }
    parameter_schema = yaml.safe_load(
        (LPM_DIRECTORY / "exp_shifted" / "params.yaml").read_text(encoding="utf-8")
    )
    priors = {
        parameter["name"]: parameter["prior"]
        for parameter in parameter_schema["parameters"]
    }
    assert priors == EXPECTED_PRIORS


@pytest.mark.extensive
def test_ploemeur_temporal_multichain_scientific_qualification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Require convergence and coherent fitted values over all sampling dates."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    # Nested temporal outputs approach the legacy Windows path-length limit.
    # These test-owned names carry no scientific meaning, so keep them short.
    results_root = tmp_path / "r"
    config = tmp_path / "c.yaml"
    config.write_text(
        yaml.safe_dump(_scientific_payload(results_root), sort_keys=False),
        encoding="utf-8",
    )

    case_directory = run_temporal(config)
    expected_mode_directory = (
        results_root / "ploemeur_temporal_multichain" / DATA.stem / "span"
    )
    assert case_directory == expected_mode_directory / "span_full"
    method_directory = case_directory / "exp_shifted"
    chain_directories = sorted((method_directory / "chains").glob("chain_*"))
    assert [directory.name for directory in chain_directories] == [
        f"chain_{chain_id:03d}" for chain_id in range(1, CHAIN_COUNT + 1)
    ]
    chains = [
        read_distribution(directory / "lpm_dist_calibrated.txt")
        for directory in chain_directories
    ]
    assert [len(chain) for chain in chains] == [RETAINED_PER_CHAIN] * CHAIN_COUNT

    pooled = read_distribution(method_directory / "lpm_dist_calibrated.txt")
    assert len(pooled) == CHAIN_COUNT * RETAINED_PER_CHAIN
    assert np.isfinite(pooled.select_dtypes(include="number")).all().all()
    assert pooled["param_in_bounds"].eq(1.0).all()
    assert pooled["mu"].between(0.1, 70.0, inclusive="both").all()
    assert pooled["shift"].between(0.0, 70.0, inclusive="both").all()
    assert pooled["mu"].quantile(0.005) > 0.1
    assert pooled["shift"].quantile(0.005) > 0.0
    np.testing.assert_allclose(
        pooled["mean"], pooled["mu"] + pooled["shift"], rtol=2.0e-12, atol=2.0e-12
    )
    np.testing.assert_allclose(pooled["std"], pooled["mu"], rtol=2.0e-12)
    for name, probability in (
        ("p10", 0.10),
        ("p25", 0.25),
        ("p50", 0.50),
        ("p75", 0.75),
        ("p90", 0.90),
    ):
        np.testing.assert_allclose(
            pooled[name],
            pooled["shift"] - np.log1p(-probability) * pooled["mu"],
            rtol=2.0e-12,
            atol=2.0e-12,
        )

    diagnostics = pd.read_table(method_directory / "mcmc_diagnostics.tsv")
    assert tuple(diagnostics["parameter"]) == DIAGNOSTIC_NAMES
    included = diagnostics.loc[diagnostics["included_in_qualification"]]
    assert not included.empty
    assert included["qualified"].all()
    assert (included["rhat"] < MAX_RHAT).all()
    assert (included["bulk_ess"] >= MIN_ESS).all()
    assert (included["tail_ess"] >= MIN_ESS).all()
    relative_mcse = included["mcse_mean"] / included["posterior_sd"]
    assert np.isfinite(relative_mcse).all()
    assert (relative_mcse <= MAX_RELATIVE_MCSE).all()

    covariance = pd.read_table(
        method_directory / "proposal_covariance.tsv", index_col=0
    )
    assert covariance.index.tolist() == ["mu", "shift"]
    assert covariance.columns.tolist() == ["mu", "shift"]
    covariance_values = covariance.to_numpy(dtype=float)
    assert np.isfinite(covariance_values).all()
    np.testing.assert_allclose(
        covariance_values,
        covariance_values.T,
        rtol=0.0,
        atol=1.0e-14,
    )
    assert np.all(np.linalg.eigvalsh(covariance_values) > 0.0)

    chain_metadata = [
        _read_key_values(directory / "chain_metadata.txt")
        for directory in chain_directories
    ]
    acceptance_rates = np.asarray(
        [float(metadata["acceptance_rate"]) for metadata in chain_metadata]
    )
    assert np.all(
        (acceptance_rates >= MIN_ACCEPTANCE_RATE)
        & (acceptance_rates <= MAX_ACCEPTANCE_RATE)
    )
    assert len({metadata["seed"] for metadata in chain_metadata}) == CHAIN_COUNT
    starts = {
        (float(metadata["initial_mu"]), float(metadata["initial_shift"]))
        for metadata in chain_metadata
    }
    assert len(starts) == CHAIN_COUNT

    parameters = _read_key_values(method_directory / "parameters_calibration.txt")
    assert parameters["prior_option"] == "True"
    assert parameters["prior_type"] == "parametric"
    assert parameters["prior_distribution_mu"] == "normal"
    assert parameters["prior_distribution_shift"] == "normal"
    assert json.loads(parameters["prior_parameters_mu"]) == [25.0, 5.0]
    assert json.loads(parameters["prior_parameters_shift"]) == [10.0, 2.0]
    assert parameters["initialization_strategy"] == "bounds_stratified"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"
    results = _read_key_values(method_directory / "results_calibration.txt")
    assert results["qualification_status"] == "qualified"
    assert results["pooling_written"] == "True"

    observations = Concentrations.from_file(DATA)
    if observations.frame["error"].min() == 0:
        observations.set_relative_errors(0.20)
    resolve_observation_errors(
        observations,
        missing_error_relative_fraction=0.01,
    )
    assert observations.frame["date"].nunique() == 20
    observation_keys = observations.observation_keys()
    assert len(observation_keys) == 58
    observed = observations.frame["concentration"].to_numpy(dtype=float)
    errors = observations.frame["error"].to_numpy(dtype=float)
    predictions = pooled[observation_keys].to_numpy(dtype=float)
    stored_objective = np.sqrt(
        np.mean(np.square((predictions - observed) / errors), axis=1)
    )
    np.testing.assert_allclose(
        pooled["obj_function"], stored_objective, rtol=2.0e-12, atol=2.0e-12
    )

    problem = CalibrationProblem(
        observations,
        "exp_shifted",
        lpm_directory=LPM_DIRECTORY,
    ).prepare()
    representative_rows = np.linspace(0, len(pooled) - 1, CHAIN_COUNT, dtype=int)
    for position in representative_rows:
        row = pooled.iloc[position]
        chi_square, modeled = problem.objective_function(
            [row["mu"], row["shift"]],
            observed,
            errors,
            return_concentrations=True,
        )
        np.testing.assert_allclose(
            modeled,
            row[observation_keys].to_numpy(dtype=float),
            rtol=2.0e-12,
            atol=2.0e-12,
        )
        assert math.sqrt(chi_square / len(observed)) == pytest.approx(
            row["obj_function"], rel=2.0e-12, abs=2.0e-12
        )

    posterior_median_fitted = np.median(predictions, axis=0)
    normalized_residuals = (posterior_median_fitted - observed) / errors
    assert np.sqrt(np.mean(np.square(normalized_residuals))) <= 1.10
    assert np.max(np.abs(normalized_residuals)) <= 5.0
    default_chi_square = problem.objective_function([10.0, 10.0], observed, errors)
    default_objective = math.sqrt(default_chi_square / len(observed))
    assert pooled["obj_function"].median() < default_objective

    mode_directory = case_directory.parent
    assert mode_directory == expected_mode_directory
    manifest = json.loads(
        (mode_directory / "result_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete"
    assert manifest["workflow"] == "temporal"
    assert manifest["details"]["mode"] == "span"
    assert manifest["details"]["dataset"] == DATA.name
    assert manifest["details"]["lpms"] == ["exp_shifted"]
    assert manifest["details"]["case_directories"] == ["span_full"]
    error_policy = manifest["details"]["observation_error_policy"]
    assert error_policy["error_rel"] == 0.20
    assert error_policy["missing_error_rel"] == 0.01
    assert error_policy["transformations"] == [
        {
            "method": "observation_fraction",
            "fraction": 0.20,
            "row_indices": list(range(58)),
            "rows_updated": 58,
        }
    ]
    diagnostic_artifact = "span_full/exp_shifted/mcmc_diagnostics.tsv"
    assert diagnostic_artifact in manifest["artifacts_sha256"]
