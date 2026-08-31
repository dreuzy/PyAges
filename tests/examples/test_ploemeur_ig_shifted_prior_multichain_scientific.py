# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Qualification of prior-active, three-parameter multi-chain MH."""

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
from pyages.data_io.lpm_distribution import read_distribution
from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date
from pyages.workflows.single_date.config import load_params_payload

ROOT = Path(__file__).resolve().parents[2]
CONFIG = (
    ROOT
    / "examples"
    / "natural"
    / "ploemeur"
    / "exemple_ploemeur_ig_shifted_prior_multichain.yaml"
)
DATA = ROOT / "examples/natural/ploemeur/data/ploemeur_F09_2010.txt"
LPM_DIRECTORY = ROOT / "data_core/data_lpm"

CHAIN_COUNT = 5
PRODUCTION_STEPS = 15_000
BURN_IN = 0.20
RETAINED_PER_CHAIN = PRODUCTION_STEPS - math.floor(BURN_IN * PRODUCTION_STEPS) - 1
MAX_RHAT = 1.01
MIN_ESS = 300.0
MAX_RELATIVE_MCSE = 0.10
PARAMETERS = ("mu", "sigma", "shift")
DIAGNOSTIC_NAMES = PARAMETERS + (
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


def _scientific_payload() -> dict:
    """Load and check the exact maintained prior-active protocol."""
    payload = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    payload["dataset"]["data_dir"] = str(DATA.parent)
    payload["dataset"]["verbose"] = False
    payload["lpm"]["data_directory"] = str(LPM_DIRECTORY)
    assert payload["dataset"]["missing_error_rel"] == 0.20
    assert payload["lpm"]["model_name"] == "ig_shifted"
    mh = payload["calibration_metropolis_hastings"]
    assert (mh["nstep"], mh["burn_in"], mh["nskip"]) == (
        PRODUCTION_STEPS,
        BURN_IN,
        1,
    )
    assert mh["prior_option"] is True
    multichain = mh["multichain"]
    assert (multichain["chains"], multichain["master_seed"]) == (
        CHAIN_COUNT,
        20260831,
    )
    assert multichain["initialization"]["strategy"] == "prior_sample"
    assert multichain["pilot"] == {
        "enabled": True,
        "nstep": 5_000,
        "burn_in": 0.75,
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


def test_ploemeur_ig_shifted_prior_multichain_protocol() -> None:
    """Keep the maintained YAML on the validated prior-sampling path."""
    params = load_params_payload(ROOT, _scientific_payload())
    assert params.lpm_model_name == "ig_shifted"
    assert params.mh_prior_option is True
    assert params.mh_multichain.initialization.strategy == "prior_sample"
    assert params.mh_multichain.pilot.nstep == 5_000
    assert params.mh_multichain.pilot.burn_in == 0.75


@pytest.mark.extensive
def test_ploemeur_ig_shifted_prior_multichain_qualification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Qualify convergence, prior provenance, and joint forward consistency.

    This field-data check has no known parameter truth. It deliberately records
    the posterior's contact with the upper ``sigma`` support instead of
    presenting numerical convergence as evidence of identifiability.
    """
    monkeypatch.setenv("MPLBACKEND", "Agg")
    config = tmp_path / "ploemeur_ig_shifted_prior_multichain.yaml"
    config.write_text(
        yaml.safe_dump(_scientific_payload(), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "ploemeur_ig_shifted_prior_multichain"
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

    assert single_date.run_single_date(config, force_inline=False) == output

    mh_directory = output / "Metropolis_Hastings"
    chain_directories = sorted((mh_directory / "chains").glob("chain_*"))
    assert len(chain_directories) == CHAIN_COUNT
    chains = [
        read_distribution(directory / "lpm_dist_calibrated.txt")
        for directory in chain_directories
    ]
    assert [len(chain) for chain in chains] == [RETAINED_PER_CHAIN] * CHAIN_COUNT

    pooled = read_distribution(mh_directory / "lpm_dist_calibrated.txt")
    assert len(pooled) == CHAIN_COUNT * RETAINED_PER_CHAIN
    assert np.isfinite(pooled.select_dtypes(include="number")).all().all()
    assert pooled["param_in_bounds"].eq(1.0).all()
    assert pooled["mu"].between(0.1, 100.0, inclusive="both").all()
    assert pooled["sigma"].between(0.1, 30.0, inclusive="both").all()
    # The active prior narrows the physical shift bound from 50 to 30 years.
    assert pooled["shift"].between(0.1, 30.0, inclusive="both").all()
    np.testing.assert_allclose(pooled["mean"], pooled["mu"] + pooled["shift"])
    np.testing.assert_allclose(pooled["std"], pooled["sigma"])

    # This is documented upper-support contact, not a sensitivity experiment or
    # a claim that sigma is well identified: posterior mass approaches 30 years.
    assert pooled["sigma"].quantile(0.975) > 28.5

    diagnostics = pd.read_table(mh_directory / "mcmc_diagnostics.tsv")
    assert tuple(diagnostics["parameter"]) == DIAGNOSTIC_NAMES
    assert diagnostics["included_in_qualification"].all()
    assert diagnostics["qualified"].all()
    assert (diagnostics["rhat"] < MAX_RHAT).all()
    assert (diagnostics["bulk_ess"] >= MIN_ESS).all()
    assert (diagnostics["tail_ess"] >= MIN_ESS).all()
    relative_mcse = diagnostics["mcse_mean"] / diagnostics["posterior_sd"]
    assert np.isfinite(relative_mcse).all()
    assert (relative_mcse <= MAX_RELATIVE_MCSE).all()

    chain_metadata = [
        _read_key_values(directory / "chain_metadata.txt")
        for directory in chain_directories
    ]
    acceptance_rates = np.asarray(
        [float(metadata["acceptance_rate"]) for metadata in chain_metadata]
    )
    assert np.all((acceptance_rates >= 0.20) & (acceptance_rates <= 0.40))
    assert len({metadata["seed"] for metadata in chain_metadata}) == CHAIN_COUNT

    parameters = _read_key_values(mh_directory / "parameters_calibration.txt")
    assert parameters["prior_option"] == "True"
    assert parameters["prior_type"] == "parametric"
    assert parameters["initialization_strategy"] == "prior_sample"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"
    assert parameters["pilot_requested_proposal_multiplier"] == "auto"
    expected_priors = {
        "mu": "[0.0, 100.0]",
        "sigma": "[0.0, 30.0]",
        "shift": "[0.0, 30.0]",
    }
    for name, prior_parameters in expected_priors.items():
        assert parameters[f"prior_distribution_{name}"] == "uniform"
        assert parameters[f"prior_parameters_{name}"] == prior_parameters

    covariance_frame = pd.read_table(
        mh_directory / "proposal_covariance.tsv",
        index_col=0,
    )
    assert covariance_frame.index.tolist() == list(PARAMETERS)
    assert covariance_frame.columns.tolist() == list(PARAMETERS)
    covariance = covariance_frame.to_numpy(dtype=float)
    assert covariance.shape == (3, 3)
    assert np.isfinite(covariance).all()
    np.testing.assert_allclose(covariance, covariance.T, rtol=0.0, atol=1.0e-14)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)

    pilot_metadata = _read_key_values(mh_directory / "pilot/pilot_metadata.txt")
    pilot_starts = np.asarray(
        [
            [
                float(pilot_metadata[f"chain_{chain_id:03d}_initial_{name}"])
                for name in PARAMETERS
            ]
            for chain_id in range(1, CHAIN_COUNT + 1)
        ]
    )
    assert len(np.unique(pilot_starts, axis=0)) == CHAIN_COUNT
    lower = np.asarray([0.1, 0.1, 0.1])
    upper = np.asarray([100.0, 30.0, 30.0])
    assert np.all((pilot_starts >= lower) & (pilot_starts <= upper))
    # Independent random draws do not guarantee stratification in general;
    # this verifies that the maintained fixed seed nevertheless exercises a
    # broadly dispersed set in every native coordinate.
    assert np.all(np.ptp(pilot_starts, axis=0) >= 0.5 * (upper - lower))

    observations = Concentrations.from_file(DATA)
    assert observations.frame["error"].eq(0.0).all()
    resolve_observation_errors(
        observations,
        missing_error_relative_fraction=0.20,
    )
    observation_keys = observations.observation_keys()
    observed = observations.frame["concentration"].to_numpy(dtype=float)
    errors = observations.frame["error"].to_numpy(dtype=float)
    np.testing.assert_allclose(
        errors,
        [25.121950626080036, 50.65128757576007, 6.453450641400011],
        rtol=1.0e-12,
        atol=0.0,
    )
    predictions = pooled[observation_keys].to_numpy(dtype=float)
    stored_objective = np.sqrt(
        np.mean(np.square((predictions - observed) / errors), axis=1)
    )
    np.testing.assert_allclose(
        pooled["obj_function"],
        stored_objective,
        rtol=2.0e-12,
        atol=2.0e-12,
    )
    assert pooled["obj_function"].median() < 1.0
    assert pooled["obj_function"].quantile(0.95) < 1.5

    problem = CalibrationProblem(
        observations,
        "ig_shifted",
        lpm_directory=LPM_DIRECTORY,
        missing_error_relative_fraction=0.20,
    ).prepare()
    representative_rows = np.linspace(0, len(pooled) - 1, CHAIN_COUNT, dtype=int)
    for position in representative_rows:
        row = pooled.iloc[position]
        chi_square, modeled = problem.objective_function(
            [row[name] for name in PARAMETERS],
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

    lower_prediction, upper_prediction = np.quantile(
        predictions,
        [0.025, 0.975],
        axis=0,
    )
    assert np.all((lower_prediction <= observed) & (observed <= upper_prediction))

    results = _read_key_values(mh_directory / "results_calibration.txt")
    provenance = _read_key_values(mh_directory / "ensemble_provenance.txt")
    assert results["qualification_status"] == "qualified"
    assert results["pooling_written"] == "True"
    assert provenance["master_seed"] == "20260831"
    assert provenance["qualification_status"] == "qualified"
    assert (
        len(
            {
                provenance[f"initialization_seed_{chain_id:03d}"]
                for chain_id in range(1, CHAIN_COUNT + 1)
            }
        )
        == CHAIN_COUNT
    )
    assert (
        len(
            {
                provenance[f"pilot_seed_{chain_id:03d}"]
                for chain_id in range(1, CHAIN_COUNT + 1)
            }
        )
        == CHAIN_COUNT
    )
    assert all(
        provenance[f"pilot_seed_{chain_id:03d}"]
        == provenance[f"planned_pilot_seed_{chain_id:03d}"]
        for chain_id in range(1, CHAIN_COUNT + 1)
    )
    assert (
        len(
            {
                provenance[f"production_seed_{chain_id:03d}"]
                for chain_id in range(1, CHAIN_COUNT + 1)
            }
        )
        == CHAIN_COUNT
    )
    phase_seeds = {
        provenance[f"{phase}_seed_{chain_id:03d}"]
        for phase in ("initialization", "pilot", "production")
        for chain_id in range(1, CHAIN_COUNT + 1)
    }
    assert len(phase_seeds) == 3 * CHAIN_COUNT

    manifest = json.loads((output / "result_manifest.json").read_text("utf-8"))
    assert manifest["status"] == "complete"
    assert "Metropolis_Hastings/mcmc_diagnostics.tsv" in manifest["artifacts_sha256"]
    assert manifest["details"]["observation_error_policy"] == {
        "missing_error_rel": 0.20,
        "transformations": [
            {
                "method": "tracer_mean_fraction",
                "fraction": 0.20,
                "row_indices": [0, 1, 2],
                "rows_updated": 3,
            }
        ],
    }
