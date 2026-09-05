# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Exploratory multi-chain characterization of Albuquerque SSW 2007.

This field case has four latent shape parameters but only three tracer
observations.  The test therefore qualifies execution, provenance, posterior
row integrity, and in-sample predictive coherence without claiming a unique
hydrogeologic solution.  Its provisional uncertainty and age-support choices
are documented beside the versioned YAML profile.
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
from pyages.data_io.lpm_distribution import read_distribution
from pyages.lpm import build_lpm
from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIRECTORY = ROOT / "examples" / "natural" / "albuquerque"
TEACHING_CONFIG = EXAMPLE_DIRECTORY / "exemple_albuquerque_shapefree.yaml"
MULTICHAIN_CONFIG = EXAMPLE_DIRECTORY / "exemple_albuquerque_shapefree_multichain.yaml"
OBSERVATIONS = EXAMPLE_DIRECTORY / "data" / "SSW_2007.txt"
LPM_DIRECTORY = EXAMPLE_DIRECTORY / "data_lpm"

CHAIN_COUNT = 5
PRODUCTION_STEPS = 2_500
BURN_IN = 0.20
RETAINED_PER_CHAIN = PRODUCTION_STEPS - math.floor(BURN_IN * PRODUCTION_STEPS) - 1
PARAMETER_NAMES = ["z1", "z2", "z3", "z4"]


def _read_key_values(path: Path) -> dict[str, str]:
    """Read the two-column calibration metadata format."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _scientific_payload() -> dict:
    """Load and pin the maintained exploratory protocol used by this test."""
    teaching = yaml.safe_load(TEACHING_CONFIG.read_text(encoding="utf-8"))
    assert "multichain" not in teaching["calibration_metropolis_hastings"]

    payload = yaml.safe_load(MULTICHAIN_CONFIG.read_text(encoding="utf-8"))
    payload["dataset"]["data_dir"] = str(OBSERVATIONS.parent)
    payload["dataset"]["verbose"] = False
    payload["lpm"]["data_directory"] = str(LPM_DIRECTORY)
    mh = payload["calibration_metropolis_hastings"]
    multichain = mh["multichain"]
    assert (mh["nstep"], mh["burn_in"], mh["nskip"]) == (
        PRODUCTION_STEPS,
        BURN_IN,
        1,
    )
    assert mh["prior_option"] is True
    assert (multichain["chains"], multichain["master_seed"]) == (
        CHAIN_COUNT,
        20260904,
    )
    assert multichain["initialization"]["strategy"] == "bounds_stratified"
    assert multichain["pilot"] == {
        "enabled": True,
        "nstep": 1_000,
        "burn_in": 0.5,
        "relative_ridge": 1.0e-6,
        "proposal_multiplier": "auto",
        "save_samples": False,
    }
    assert multichain["diagnostics"] == {
        "max_rhat": 1.10,
        "min_bulk_ess": 50,
        "min_tail_ess": 50,
        "require_convergence": False,
    }
    return payload


@pytest.mark.extensive
def test_albuquerque_shapefree_multichain_scientific_characterization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Characterize a reproducible field posterior without asserting uniqueness."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    config = tmp_path / "albuquerque_shapefree_multichain_exploratory.yaml"
    config.write_text(
        yaml.safe_dump(_scientific_payload(), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "albuquerque_shapefree_multichain_exploratory"
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
    assert pooled[PARAMETER_NAMES].ge(-8.0).all().all()
    assert pooled[PARAMETER_NAMES].le(8.0).all().all()

    diagnostics = pd.read_table(mh_directory / "mcmc_diagnostics.tsv")
    included = diagnostics.loc[diagnostics["included_in_qualification"]]
    diagnosed_parameters = included.loc[included["parameter"].isin(PARAMETER_NAMES)]
    assert diagnosed_parameters["parameter"].tolist() == PARAMETER_NAMES
    assert (
        np.isfinite(included[["rhat", "bulk_ess", "tail_ess", "mcse_mean"]]).all().all()
    )
    assert (included["rhat"] >= 1.0).all()
    assert (included[["bulk_ess", "tail_ess"]] > 0.0).all().all()
    # This profile is expected to expose inadequate mixing, not to turn a
    # weakly identified field target into a qualified posterior.
    assert not included["qualified"].all()

    metadata = [
        _read_key_values(directory / "chain_metadata.txt")
        for directory in chain_directories
    ]
    assert len({item["seed"] for item in metadata}) == CHAIN_COUNT
    acceptance = np.asarray([float(item["acceptance_rate"]) for item in metadata])
    assert np.all((acceptance >= 0.05) & (acceptance <= 0.80))
    production_starts = np.asarray(
        [
            [float(item[f"initial_{name}"]) for name in PARAMETER_NAMES]
            for item in metadata
        ]
    )
    assert len(np.unique(production_starts, axis=0)) == CHAIN_COUNT

    parameters = _read_key_values(mh_directory / "parameters_calibration.txt")
    assert parameters["initialization_strategy"] == "bounds_stratified"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"
    pilot_metadata = _read_key_values(mh_directory / "pilot" / "pilot_metadata.txt")
    pilot_starts = np.asarray(
        [
            [
                float(pilot_metadata[f"chain_{chain_id:03d}_initial_{name}"])
                for name in PARAMETER_NAMES
            ]
            for chain_id in range(1, CHAIN_COUNT + 1)
        ]
    )
    assert len(np.unique(pilot_starts, axis=0)) == CHAIN_COUNT
    assert np.all(np.ptp(pilot_starts, axis=0) >= 8.0)
    covariance_frame = pd.read_table(
        mh_directory / "proposal_covariance.tsv",
        index_col=0,
    )
    assert covariance_frame.index.tolist() == PARAMETER_NAMES
    assert covariance_frame.columns.tolist() == PARAMETER_NAMES
    covariance = covariance_frame.to_numpy(dtype=float)
    np.testing.assert_allclose(covariance, covariance.T, rtol=0.0, atol=1.0e-14)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)

    # Stick-breaking must produce a valid five-bin distribution for actual
    # posterior rows, including states far from the model defaults.
    lpm = build_lpm("shapefree_n_oldbin", directory_lpm=str(LPM_DIRECTORY))
    representative_rows = np.linspace(0, len(pooled) - 1, CHAIN_COUNT, dtype=int)
    for position in representative_rows:
        row = pooled.iloc[position]
        lpm.set_param_from_array(row[PARAMETER_NAMES].to_numpy(dtype=float))
        fractions = lpm.fractions()
        assert fractions.shape == (5,)
        assert np.all(fractions >= 0.0)
        np.testing.assert_allclose(fractions.sum(), 1.0, rtol=0.0, atol=1.0e-14)

    observations = Concentrations.from_file(OBSERVATIONS)
    assert observations.frame["error"].eq(0.0).all()
    resolve_observation_errors(
        observations,
        missing_error_relative_fraction=0.01,
    )
    observation_keys = observations.observation_keys()
    observed = observations.frame["concentration"].to_numpy(dtype=float)
    errors = observations.frame["error"].to_numpy(dtype=float)
    np.testing.assert_allclose(
        errors,
        [0.08805337771288839, 0.838136061158079, 0.30013394743977995],
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

    # Re-evaluate representative joint rows with a freshly prepared forward
    # problem. This detects accidental recombination of marginal parameters or
    # concentrations in persisted samples.
    problem = CalibrationProblem(
        observations,
        "shapefree_n_oldbin",
        lpm_directory=LPM_DIRECTORY,
    ).prepare()
    for position in representative_rows:
        row = pooled.iloc[position]
        chi_square, modeled = problem.objective_function(
            row[PARAMETER_NAMES].to_numpy(dtype=float),
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

    posterior_median = np.median(predictions, axis=0)
    normalized_residuals = (posterior_median - observed) / errors
    # The young tracers can be matched, but a distribution truncated at 120
    # years cannot reproduce the much older carbon-14 signature. This negative
    # scientific result is part of the regression contract for the provisional
    # model and prevents a numerically completed run being called adequate.
    assert np.abs(normalized_residuals[[0, 2]]).max() <= 1.0
    assert abs(normalized_residuals[1]) >= 50.0
    assert np.sqrt(np.mean(np.square(normalized_residuals))) >= 30.0
    lower_prediction = np.quantile(predictions, 0.025, axis=0)
    assert lower_prediction[1] > observed[1]
    assert pooled[["z1", "z2", "z3"]].quantile(0.005).lt(-7.8).all()

    default_chi_square = problem.objective_function(
        [0.0, 0.0, 0.0, 0.0],
        observed,
        errors,
    )
    default_objective = math.sqrt(default_chi_square / len(observed))
    assert pooled["obj_function"].median() < 0.5 * default_objective

    results = _read_key_values(mh_directory / "results_calibration.txt")
    provenance = _read_key_values(mh_directory / "ensemble_provenance.txt")
    assert results["qualification_status"] == "not_qualified"
    assert results["pooling_written"] == "True"
    assert provenance["master_seed"] == "20260904"
    assert provenance["qualification_status"] == "not_qualified"

    manifest = json.loads((output / "result_manifest.json").read_text("utf-8"))
    assert manifest["status"] == "complete"
    assert "Metropolis_Hastings/mcmc_diagnostics.tsv" in manifest["artifacts_sha256"]
    assert manifest["details"]["observation_error_policy"] == {
        "missing_error_rel": 0.01,
        "transformations": [
            {
                "method": "tracer_mean_fraction",
                "fraction": 0.01,
                "row_indices": [0, 1, 2],
                "rows_updated": 3,
            }
        ],
    }
