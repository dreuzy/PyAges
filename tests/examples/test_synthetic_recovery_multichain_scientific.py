# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Scientific multi-chain qualification of the synthetic recovery example."""

from __future__ import annotations

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
EXAMPLE = ROOT / "examples" / "synthetic" / "lpm_recovery_single_date"


def _read_key_values(path: Path) -> dict[str, str]:
    """Read a canonical two-column calibration metadata file."""
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


@pytest.mark.extensive
def test_synthetic_example_multichain_recovers_known_parameters(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Qualify convergence and recovery of the versioned known-truth case."""
    monkeypatch.setenv("MPLBACKEND", "Agg")
    teaching_source = EXAMPLE / "lpm_recovery_single_date.yaml"
    teaching_payload = yaml.safe_load(teaching_source.read_text(encoding="utf-8"))
    assert "multichain" not in teaching_payload["calibration_metropolis_hastings"]
    source = EXAMPLE / "lpm_recovery_single_date_multichain.yaml"
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))

    truth_payload = yaml.safe_load(
        (EXAMPLE / "data" / "ground_truth.yaml").read_text(encoding="utf-8")
    )
    truth = {
        name: float(value) for name, value in truth_payload["lpm"]["parameters"].items()
    }
    assert truth == {"mu": 28.0, "shift": 4.0}

    payload["dataset"]["data_dir"] = str(EXAMPLE / "data")
    payload["dataset"]["verbose"] = False
    payload["lpm"]["data_directory"] = str(ROOT / "data_core" / "data_lpm")
    mh = payload["calibration_metropolis_hastings"]
    multichain = mh["multichain"]
    assert payload["run"] == {
        "reachable_concentrations": False,
        "objective_function": False,
        "calibration_metropolis_hastings": True,
        "calibration_simplex": False,
    }
    assert (mh["nstep"], mh["burn_in"], mh["nskip"]) == (4_000, 0.25, 1)
    assert (multichain["chains"], multichain["master_seed"]) == (4, 20260831)
    assert multichain["pilot"]["nstep"] == 1_500
    assert multichain["diagnostics"] == {
        "max_rhat": 1.01,
        "min_bulk_ess": 300,
        "min_tail_ess": 300,
        "require_convergence": True,
    }
    config = tmp_path / "synthetic_multichain_scientific.yaml"
    config.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    output = tmp_path / "synthetic_multichain_scientific"
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
    diagnostics = pd.read_table(mh_directory / "mcmc_diagnostics.tsv").set_index(
        "parameter"
    )
    diagnosed = diagnostics.loc[["mu", "shift", "mean"]]
    assert diagnosed["qualified"].all()
    assert (diagnosed["rhat"] < 1.01).all()
    # The documented failure/recovery drill tightens only this gate. Keep the
    # fixed-seed profile demonstrably above that deliberately impractical limit
    # without paying for a second extensive run.
    assert diagnosed["rhat"].max() > 1.0000000000000002
    assert (diagnosed["bulk_ess"] >= 300.0).all()
    assert (diagnosed["tail_ess"] >= 300.0).all()
    assert (diagnosed["mcse_mean"] <= 0.10 * diagnosed["posterior_sd"]).all()
    results = _read_key_values(mh_directory / "results_calibration.txt")
    assert results["qualification_status"] == "qualified"

    covariance = pd.read_table(
        mh_directory / "proposal_covariance.tsv",
        index_col=0,
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

    chain_frames = [
        read_distribution(
            mh_directory
            / "chains"
            / f"chain_{chain_id:03d}"
            / "lpm_dist_calibrated.txt"
        )
        for chain_id in range(1, 5)
    ]
    assert [len(frame) for frame in chain_frames] == [2_999] * 4
    chain_metadata = [
        _read_key_values(
            mh_directory / "chains" / f"chain_{chain_id:03d}" / "chain_metadata.txt"
        )
        for chain_id in range(1, 5)
    ]
    initial_states = {
        (float(metadata["initial_mu"]), float(metadata["initial_shift"]))
        for metadata in chain_metadata
    }
    assert len(initial_states) == 4
    assert all(
        0.1 <= mu <= 70.0 and 0.0 <= shift <= 70.0 for mu, shift in initial_states
    )
    parameters = _read_key_values(mh_directory / "parameters_calibration.txt")
    assert parameters["initialization_strategy"] == "bounds_stratified"
    assert parameters["pilot_covariance_mode"] == "pooled_within_chain"

    pooled = read_distribution(mh_directory / "lpm_dist_calibrated.txt")
    assert len(pooled) == 11_996
    for parameter, true_value in truth.items():
        values = pooled[parameter].to_numpy(dtype=float)
        lower, upper = np.quantile(values, (0.025, 0.975))
        assert lower <= true_value <= upper
        posterior_mean = float(np.mean(values))
        posterior_sd = float(np.std(values, ddof=1))
        assert abs(posterior_mean - true_value) <= 2.0 * posterior_sd

    # mu and shift are strongly anticorrelated in this inverse problem.  The
    # joint ellipse and their identifiable sum therefore complement marginal
    # interval checks without pretending that the two estimates are independent.
    parameter_names = ["mu", "shift"]
    posterior = pooled[parameter_names].to_numpy(dtype=float)
    true_vector = np.array([truth[name] for name in parameter_names])
    mean_error = np.mean(posterior, axis=0) - true_vector
    posterior_covariance = np.cov(posterior, rowvar=False, ddof=1)
    squared_mahalanobis = float(
        mean_error @ np.linalg.solve(posterior_covariance, mean_error)
    )
    assert squared_mahalanobis <= 5.991  # 95% chi-square threshold, two dimensions

    total_age = pooled["mu"].to_numpy() + pooled["shift"].to_numpy()
    true_total_age = truth["mu"] + truth["shift"]
    total_interval = np.quantile(total_age, (0.025, 0.975))
    assert total_interval[0] <= true_total_age <= total_interval[1]
    assert abs(float(np.mean(total_age)) - true_total_age) <= 2.0 * float(
        np.std(total_age, ddof=1)
    )

    true_concentrations = {
        row["element"]: float(row["concentration"])
        for row in truth_payload["true_concentrations"]
    }
    observations = {
        row["element"]: row for row in truth_payload["observed_concentrations"]
    }
    for tracer, true_concentration in true_concentrations.items():
        concentration_columns = [
            name for name in pooled.columns if name.startswith(f"{tracer}@")
        ]
        assert len(concentration_columns) == 1
        fitted_mean = float(np.mean(pooled[concentration_columns[0]]))
        observed = observations[tracer]
        observed_error = float(observed["error"])
        assert abs(fitted_mean - true_concentration) <= observed_error
        assert abs(fitted_mean - float(observed["concentration"])) <= (
            2.0 * observed_error
        )
