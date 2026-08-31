# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Extensive multi-chain qualification of the natural Ploemeur example.

The field observations have no known parameter truth.  Consequently this test
does not perform parameter recovery.  It instead qualifies MCMC convergence,
joint-sample integrity, parameter support, and in-sample coherence of fitted
latent concentrations for the historical F09 single-date example.
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
from pyages.workflows.single_date import context as single_context
from pyages.workflows.single_date import reporting as single_reporting
from pyages.workflows.single_date import runner as single_date

ROOT = Path(__file__).resolve().parents[2]
PLOEMEUR_CONFIG = ROOT / "examples" / "natural" / "ploemeur" / "exemple_ploemeur.yaml"
PLOEMEUR_MULTICHAIN_CONFIG = (
    ROOT / "examples" / "natural" / "ploemeur" / "exemple_ploemeur_multichain.yaml"
)
PLOEMEUR_DATA = (
    ROOT / "examples" / "natural" / "ploemeur" / "data" / "ploemeur_F09_2010.txt"
)
LPM_DIRECTORY = ROOT / "data_core" / "data_lpm"

CHAIN_COUNT = 5
PRODUCTION_STEPS = 5_000
BURN_IN = 0.20
RETAINED_PER_CHAIN = PRODUCTION_STEPS - math.floor(BURN_IN * PRODUCTION_STEPS) - 1
MAX_RHAT = 1.01
MIN_ESS = 300.0
MAX_RELATIVE_MCSE = 0.10


def _read_key_values(path: Path) -> dict[str, str]:
    """Read the canonical two-column calibration metadata format."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _scientific_payload() -> dict:
    """Load the same versioned protocol exposed to users and documentation."""
    teaching_payload = yaml.safe_load(PLOEMEUR_CONFIG.read_text(encoding="utf-8"))
    assert "multichain" not in teaching_payload["calibration_metropolis_hastings"]
    payload = yaml.safe_load(PLOEMEUR_MULTICHAIN_CONFIG.read_text(encoding="utf-8"))
    payload["dataset"]["data_dir"] = str(PLOEMEUR_DATA.parent)
    payload["dataset"]["verbose"] = False
    payload["lpm"]["data_directory"] = str(LPM_DIRECTORY)
    assert payload["run"] == {
        "reachable_concentrations": False,
        "objective_function": False,
        "calibration_metropolis_hastings": True,
        "calibration_simplex": False,
    }
    mh = payload["calibration_metropolis_hastings"]
    multichain = mh["multichain"]
    assert (mh["nstep"], mh["burn_in"], mh["nskip"]) == (
        PRODUCTION_STEPS,
        BURN_IN,
        1,
    )
    assert (multichain["chains"], multichain["master_seed"]) == (
        CHAIN_COUNT,
        20260831,
    )
    assert multichain["pilot"]["nstep"] == 2_000
    assert multichain["diagnostics"] == {
        "max_rhat": MAX_RHAT,
        "min_bulk_ess": MIN_ESS,
        "min_tail_ess": MIN_ESS,
        "require_convergence": True,
    }
    return payload


@pytest.mark.extensive
def test_ploemeur_f09_multichain_scientific_qualification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Require convergence and coherent predictions on the natural F09 data.

    Fitted-concentration checks are deliberately described as *in-sample*:
    they establish that posterior forward-model values explain the three
    observations used in the likelihood. They neither simulate replicated
    observation noise nor turn field parameters into known ground truth, and
    do not prove that this LPM is unique or adequate beyond this example.
    """
    monkeypatch.setenv("MPLBACKEND", "Agg")
    config = tmp_path / "ploemeur_f09_multichain_scientific.yaml"
    config.write_text(
        yaml.safe_dump(_scientific_payload(), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "ploemeur_f09_multichain_scientific"
    monkeypatch.setattr(
        single_context,
        "dataset_results_directory",
        lambda _name, **_kwargs: output,
    )
    # Chronicle rendering is unrelated to inference and fitted-value checks
    # below; disabling it keeps this extensive test headless and focused.
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
    assert pooled["mu"].between(0.1, 70.0, inclusive="both").all()
    assert pooled["shift"].between(0.0, 70.0, inclusive="both").all()

    # No visible posterior pile-up on the declared support boundaries.  This
    # is a support/geometry check, not an assertion of true field parameters.
    assert pooled["mu"].quantile(0.005) > 0.1
    assert pooled["mu"].quantile(0.995) < 70.0
    assert pooled["shift"].quantile(0.005) > 0.0
    assert pooled["shift"].quantile(0.995) < 70.0
    np.testing.assert_allclose(
        pooled["p50"],
        pooled["shift"] + math.log(2.0) * pooled["mu"],
        rtol=2.0e-12,
        atol=2.0e-12,
    )

    diagnostics = pd.read_table(mh_directory / "mcmc_diagnostics.tsv")
    included = diagnostics.loc[diagnostics["included_in_qualification"]]
    assert not included.empty
    assert included["qualified"].all()
    assert (included["rhat"] < MAX_RHAT).all()
    assert (included["bulk_ess"] >= MIN_ESS).all()
    assert (included["tail_ess"] >= MIN_ESS).all()
    relative_mcse = included["mcse_mean"] / included["posterior_sd"]
    assert np.isfinite(relative_mcse).all()
    assert (relative_mcse <= MAX_RELATIVE_MCSE).all()

    chain_metadata = [
        _read_key_values(directory / "chain_metadata.txt")
        for directory in chain_directories
    ]
    acceptance_rates = np.asarray(
        [float(metadata["success_rate"]) for metadata in chain_metadata]
    )
    assert np.all((acceptance_rates >= 0.20) & (acceptance_rates <= 0.50))
    assert len({metadata["seed"] for metadata in chain_metadata}) == CHAIN_COUNT
    initial_states = {
        (float(metadata["initial_mu"]), float(metadata["initial_shift"]))
        for metadata in chain_metadata
    }
    assert len(initial_states) == CHAIN_COUNT
    assert all(
        0.1 <= mu <= 70.0 and 0.0 <= shift <= 70.0 for mu, shift in initial_states
    )
    parameters = _read_key_values(mh_directory / "parameters_calibration.txt")
    assert parameters["initialization_strategy"] == "bounds_stratified"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"

    covariance = pd.read_table(
        mh_directory / "proposal_covariance.tsv",
        index_col=0,
    ).to_numpy(dtype=float)
    assert covariance.shape == (2, 2)
    assert np.all(np.linalg.eigvalsh(covariance) > 0.0)

    pilot_metadata = _read_key_values(mh_directory / "pilot" / "pilot_metadata.txt")
    pilot_starts = np.asarray(
        [
            [
                float(pilot_metadata[f"chain_{chain_id:03d}_initial_mu"]),
                float(pilot_metadata[f"chain_{chain_id:03d}_initial_shift"]),
            ]
            for chain_id in range(1, CHAIN_COUNT + 1)
        ]
    )
    assert len(np.unique(pilot_starts, axis=0)) == CHAIN_COUNT
    # Latin-hypercube starts deliberately cover at least half of each bounded
    # dimension before the pilot brings the chains towards the posterior.
    assert np.ptp(pilot_starts[:, 0]) >= 0.5 * (70.0 - 0.1)
    assert np.ptp(pilot_starts[:, 1]) >= 0.5 * (70.0 - 0.0)

    observations = Concentrations.from_file(PLOEMEUR_DATA)
    resolve_observation_errors(observations)
    observation_keys = observations.observation_keys()
    observed = observations.frame["concentration"].to_numpy(dtype=float)
    errors = observations.frame["error"].to_numpy(dtype=float)
    predictions = pooled[observation_keys].to_numpy(dtype=float)

    # Every saved objective must still belong to the same complete prediction
    # row; this prevents scientifically invalid recombination of marginals.
    stored_objective = np.sqrt(
        np.mean(np.square((predictions - observed) / errors), axis=1)
    )
    np.testing.assert_allclose(
        pooled["obj_function"],
        stored_objective,
        rtol=2.0e-12,
        atol=2.0e-12,
    )

    # Independently re-run representative posterior rows through the forward
    # operator, rather than trusting only the concentrations serialized by MH.
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
    assert np.sqrt(np.mean(np.square(normalized_residuals))) <= 1.50
    assert np.max(np.abs(normalized_residuals)) <= 2.0
    lower_prediction, upper_prediction = np.quantile(
        predictions,
        [0.025, 0.975],
        axis=0,
    )
    assert np.all((lower_prediction <= observed) & (observed <= upper_prediction))

    # The posterior should improve materially on the canonical model defaults
    # without relying on a supposed true parameter vector for this field case.
    default_chi_square = problem.objective_function([10.0, 10.0], observed, errors)
    default_objective = math.sqrt(default_chi_square / len(observed))
    assert pooled["obj_function"].median() < 0.5 * default_objective

    results = _read_key_values(mh_directory / "results_calibration.txt")
    provenance = _read_key_values(mh_directory / "ensemble_provenance.txt")
    assert results["qualification_status"] == "qualified"
    assert results["pooling_written"] == "True"
    assert provenance["master_seed"] == "20260831"
    assert provenance["qualification_status"] == "qualified"

    manifest = json.loads((output / "result_manifest.json").read_text("utf-8"))
    assert manifest["status"] == "complete"
    assert "Metropolis_Hastings/mcmc_diagnostics.tsv" in manifest["artifacts_sha256"]
