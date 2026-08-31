# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Serialization contracts for multi-chain MH results."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble import MultiChainMetropolisHastings
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
    build_seed_plan,
)
from pyages.calibration.methods.mh.results import (
    DIAGNOSTICS_UNAVAILABLE,
    NOT_QUALIFIED,
    QUALIFIED,
    MHChainResult,
    MHParameterDiagnostics,
    MHPilotResult,
    MHRunRecord,
)
from pyages.calibration.methods.mh.sampler import MetropolisHastings
from pyages.calibration.problem import CalibrationProblem
from pyages.convolution import ConvolutionTracers
from pyages.data_io import mh_results
from pyages.data_io.lpm_distribution import read_distribution, read_frame
from pyages.data_io.mh_results import (
    clear_mh_ensemble_artifacts,
    write_mh_ensemble_result,
)
from pyages.lpm import build_lpm
from pyages.lpm.samples.table import LpmSampleTable


def _configs(
    *,
    save_pilot_samples: bool = True,
    require_convergence: bool = True,
) -> tuple[MHConfig, MHEnsembleConfig]:
    chain_config = MHConfig(
        nstep=20,
        burn_in=0.1,
        nskip=2,
        prior_option=True,
        monitor=False,
    )
    ensemble_config = MHEnsembleConfig(
        chains=2,
        master_seed=7123,
        initialization=MHInitializationConfig(strategy="model_default"),
        pilot=MHPilotConfig(
            enabled=True,
            nstep=10,
            burn_in=0.2,
            proposal_multiplier=0.75,
            save_samples=save_pilot_samples,
        ),
        diagnostics=MHDiagnosticsConfig(
            max_rhat=1.05,
            min_bulk_ess=10,
            min_tail_ess=10,
            require_convergence=require_convergence,
        ),
    )
    return chain_config, ensemble_config


def _samples(offset: float) -> LpmSampleTable:
    model = build_lpm("exp")
    parameter = model.get_param_names()[0]
    table = LpmSampleTable(model, c_names=["tracer"])
    for index in range(8):
        value = offset + index + 1.0
        table.append_sample(
            {parameter: value},
            obj_function=value**2,
            concentrations=[value / 10.0],
        )
    table.add_moments()
    return table


def _result(
    status: str,
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    *,
    save_pilot_samples: bool = True,
) -> MHRunRecord:
    first = _samples(0.0)
    second = _samples(10.0)
    parameter = first.get_param_names()[0]
    seed_plan = build_seed_plan(ensemble_config)
    seeds = seed_plan.production_seeds
    chains = (
        MHChainResult(
            chain_id=1,
            seed=seeds[0],
            initial_params={parameter: 1.1},
            samples=first,
            acceptance_rate=0.4,
            runtime_seconds=1.25,
        ),
        MHChainResult(
            chain_id=2,
            seed=seeds[1],
            initial_params={parameter: 10.9},
            samples=second,
            acceptance_rate=0.6,
            runtime_seconds=1.75,
        ),
    )
    qualified = status == QUALIFIED
    diagnostic = MHParameterDiagnostics(
        parameter=parameter,
        rhat=1.005 if qualified else 1.2,
        bulk_ess=500 if qualified else 5,
        tail_ess=450 if qualified else 4,
        mcse_mean=0.01,
        posterior_sd=2.0,
        qualified=qualified,
    )
    diagnostic_names = tuple(
        dict.fromkeys(
            tuple(first.get_param_names()) + tuple(first.lpm_template.moments_name())
        )
    )
    diagnostics = tuple(
        replace(
            diagnostic,
            parameter=name,
            rhat=1.005,
            bulk_ess=500,
            tail_ess=450,
            qualified=True,
        )
        if name != parameter
        else replace(diagnostic, parameter=name)
        for name in diagnostic_names
    )
    pilot_samples = (
        (
            np.linspace(1.0, 1.1, 7)[:, None],
            np.linspace(11.0, 10.9, 7)[:, None],
        )
        if save_pilot_samples
        else None
    )
    pilot = MHPilotResult(
        final_states=({parameter: 1.1}, {parameter: 10.9}),
        covariance=np.array([[0.25]]),
        proposal_multiplier=0.75,
        acceptance_rates=(0.45, 0.55),
        retained_counts=(7, 7),
        samples=pilot_samples,
        initial_states=({parameter: 1.0}, {parameter: 11.0}),
        runtime_seconds=(0.5, 0.75),
    )
    return MHRunRecord(
        chain_config=chain_config,
        ensemble_config=ensemble_config,
        chains=chains,
        pilot=pilot,
        diagnostics=diagnostics,
        qualification_status=status,
        seed_plan=seed_plan,
        target_signature_version=1,
        target_sha256="b" * 64,
        resolved_metadata={
            "pilot_MH_delta_source": "bounds",
            "pilot_MH_delta_fraction": 0.1,
            f"pilot_MH_delta_{parameter}": 9.99,
            f"prior_distribution_{parameter}": "uniform",
            f"prior_parameters_{parameter}": "[0.1, 100.0]",
        },
    )


def _read_key_values(path: Path) -> dict[str, str]:
    return dict(
        line.split("\t", maxsplit=1)
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def _write_exp_schema(data_directory: Path, *, step: float) -> Path:
    """Write a minimal valid exp schema with a selectable proposal step."""
    model_directory = data_directory / "exp"
    model_directory.mkdir(parents=True)
    path = model_directory / "params.yaml"
    path.write_text(
        f"""model: exp
version: 1
parameters:
  - name: mu
    bounds: [0.1, 100.0]
    init: 10.0
    step: {step}
    prior:
      type: uniform
      min: 0.1
      max: 100.0
""",
        encoding="utf-8",
    )
    return path


def test_writer_preserves_chains_and_emits_full_qualified_artifact_set(
    tmp_path,
) -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)

    pooled = write_mh_ensemble_result(result, tmp_path)

    assert pooled is not None
    assert len(pooled.frame) == 16
    assert len(read_distribution(tmp_path / "lpm_dist_calibrated.txt")) == 16
    assert (
        len(
            read_distribution(
                tmp_path / "chains" / "chain_001" / "lpm_dist_calibrated.txt"
            )
        )
        == 8
    )
    assert (
        len(
            read_distribution(
                tmp_path / "chains" / "chain_002" / "lpm_dist_calibrated.txt"
            )
        )
        == 8
    )
    assert (tmp_path / "chains" / "chain_001" / "chain_metadata.txt").is_file()

    diagnostics = read_frame(tmp_path / "mcmc_diagnostics.tsv", index=False)
    assert list(diagnostics.columns) == [
        "parameter",
        "rhat",
        "bulk_ess",
        "tail_ess",
        "mcse_mean",
        "posterior_sd",
        "included_in_qualification",
        "qualified",
    ]
    assert diagnostics.loc[0, "qualified"]

    covariance = read_frame(tmp_path / "proposal_covariance.tsv", index=True)
    np.testing.assert_allclose(covariance.to_numpy(), [[0.25]])
    assert (tmp_path / "pilot" / "pilot_metadata.txt").is_file()
    assert (tmp_path / "pilot" / "chain_001_samples.tsv").is_file()
    assert (tmp_path / "pilot" / "chain_002_samples.tsv").is_file()

    parameter = result.chains[0].samples.get_param_names()[0]
    assert (tmp_path / f"lpm_histo_calibrated_{parameter}.txt").is_file()
    assert (tmp_path / "lpm_stats_calibrated.txt").is_file()
    parameters = _read_key_values(tmp_path / "parameters_calibration.txt")
    assert parameters["execution_mode"] == "multi_chain"
    assert parameters["burn_in"] == str(chain_config.burn_in)
    assert "burn-in" not in parameters
    assert parameters["pilot_burn_in"] == str(ensemble_config.pilot.burn_in)
    assert "pilot_burn-in" not in parameters
    assert parameters["master_seed"] == str(ensemble_config.master_seed)
    assert parameters["seed"] == str(ensemble_config.master_seed)
    assert parameters["retained_sample_count"] == "16"
    assert parameters["pilot_MH_delta_source"] == "bounds"
    assert float(parameters["pilot_MH_delta_mu"]) > 0.0
    assert parameters["prior_distribution_mu"] == "uniform"
    assert "prior_parameters_mu" in parameters
    provenance = _read_key_values(tmp_path / "ensemble_provenance.txt")
    assert provenance["production_seed_001"] == str(result.chains[0].seed)
    assert provenance["initialization_seed_001"] == str(
        result.seed_plan.initialization_seeds[0]
    )
    assert provenance["target_signature_version"] == "1"
    assert provenance["target_sha256"] == result.target_sha256
    run_results = _read_key_values(tmp_path / "results_calibration.txt")
    assert run_results["qualification_status"] == QUALIFIED
    assert run_results["success_rate"] == "0.5"
    assert run_results["mean_acceptance_rate"] == "0.5"
    assert run_results["time_perform"] == "4.25"
    assert run_results["production_runtime_sum_seconds"] == "3.0"
    assert run_results["pilot_runtime_sum_seconds"] == "1.25"
    assert run_results["pooling_written"] == "True"
    assert run_results["pooled_sample_count"] == "16"
    pilot_metadata = _read_key_values(tmp_path / "pilot" / "pilot_metadata.txt")
    assert pilot_metadata[f"chain_001_initial_{parameter}"] == "1.0"
    assert pilot_metadata["chain_001_acceptance_rate"] == "0.45"
    chain_metadata = _read_key_values(
        tmp_path / "chains" / "chain_001" / "chain_metadata.txt"
    )
    assert chain_metadata["acceptance_rate"] == "0.4"
    assert "success_rate" not in chain_metadata


def test_writer_preserves_pre_run_file_provenance_after_sources_change(
    tmp_path,
) -> None:
    data_directory = tmp_path / "lpm_data"
    schema_path = _write_exp_schema(data_directory, step=0.2)
    prior_prefix = tmp_path / "empirical_prior"
    prior_path = tmp_path / "empirical_prior_mu.txt"
    prior_path.write_text(
        "val\thist\n1.0\t0.1\n10.0\t0.8\n20.0\t0.1\n",
        encoding="utf-8",
    )
    original_prior_sha256 = hashlib.sha256(prior_path.read_bytes()).hexdigest()

    target = build_lpm("exp", directory_lpm=str(data_directory))
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.2)

    def problem_factory(_stage: str, _chain_id: int) -> CalibrationProblem:
        return CalibrationProblem(
            observations,
            "exp",
            lpm_directory=data_directory,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()

    chain_config = MHConfig(
        nstep=12,
        burn_in=0.0,
        nskip=1,
        prior_option=True,
        prior_type="empirical",
        prior_file=str(prior_prefix),
        monitor=False,
        display_traj=False,
        display_text=False,
        componentwise_source="model",
    )
    ensemble_config = MHEnsembleConfig(
        chains=2,
        master_seed=8217,
        initialization=MHInitializationConfig(
            strategy="explicit",
            explicit_starts=({"mu": 8.0}, {"mu": 12.0}),
        ),
        pilot=MHPilotConfig(
            enabled=True,
            nstep=5,
            burn_in=0.0,
            proposal_multiplier=0.75,
            save_samples=False,
        ),
        diagnostics=MHDiagnosticsConfig(
            max_rhat=1.0e12,
            min_bulk_ess=1.0e-6,
            min_tail_ess=1.0e-6,
            require_convergence=False,
        ),
    )
    result = MultiChainMetropolisHastings(
        chain_config,
        ensemble_config,
    ).run(problem_factory)

    assert result.resolved_metadata["pilot_MH_delta_mu"] == 0.2
    assert result.resolved_metadata["prior_sha256_mu"] == original_prior_sha256

    schema_path.write_text(
        schema_path.read_text(encoding="utf-8").replace("step: 0.2", "step: 8.0"),
        encoding="utf-8",
    )
    prior_path.write_text(
        "val\thist\n1.0\t0.8\n10.0\t0.1\n20.0\t0.1\n",
        encoding="utf-8",
    )
    changed_prior_sha256 = hashlib.sha256(prior_path.read_bytes()).hexdigest()
    assert changed_prior_sha256 != original_prior_sha256

    output_directory = tmp_path / "output"
    write_mh_ensemble_result(result, output_directory)

    parameters = _read_key_values(output_directory / "parameters_calibration.txt")
    assert parameters["pilot_MH_delta_mu"] == "0.2"
    assert parameters["prior_distribution_mu"] == "empirical"
    assert parameters["prior_sha256_mu"] == original_prior_sha256
    assert parameters["prior_sha256_mu"] != changed_prior_sha256
    assert parameters["prior_grid_points_mu"] == "101"


def test_lpm_document_drift_after_initialization_is_rejected_before_transitions(
    tmp_path,
    monkeypatch,
) -> None:
    data_directory = tmp_path / "lpm_data"
    schema_path = _write_exp_schema(data_directory, step=0.2)
    target = build_lpm("exp", directory_lpm=str(data_directory))
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.2)
    schema_changed = False

    def problem_factory(stage: str, chain_id: int) -> CalibrationProblem:
        nonlocal schema_changed
        if stage == "production" and chain_id == 1 and not schema_changed:
            schema_path.write_text(
                schema_path.read_text(encoding="utf-8").replace(
                    "      max: 100.0",
                    "      max: 90.0",
                ),
                encoding="utf-8",
            )
            schema_changed = True
        return CalibrationProblem(
            observations,
            "exp",
            lpm_directory=data_directory,
            explore_objective=False,
            explore_reachable=False,
        ).prepare()

    transition_count = 0
    original_mcmc_step = MetropolisHastings._mcmc_step

    def recording_mcmc_step(self, *args, **kwargs):
        nonlocal transition_count
        transition_count += 1
        return original_mcmc_step(self, *args, **kwargs)

    monkeypatch.setattr(
        MetropolisHastings,
        "_mcmc_step",
        recording_mcmc_step,
    )
    chain_config = MHConfig(
        nstep=12,
        burn_in=0.0,
        nskip=1,
        prior_option=True,
        prior_type="parametric",
        monitor=False,
        display_traj=False,
        display_text=False,
        componentwise_source="model",
    )
    ensemble_config = MHEnsembleConfig(
        chains=2,
        master_seed=9017,
        initialization=MHInitializationConfig(
            strategy="explicit",
            explicit_starts=({"mu": 8.0}, {"mu": 12.0}),
        ),
        pilot=MHPilotConfig(enabled=False),
        diagnostics=MHDiagnosticsConfig(require_convergence=False),
    )

    with pytest.raises(
        ValueError,
        match="stage='production', chain_id=1, category='lpm'",
    ):
        MultiChainMetropolisHastings(
            chain_config,
            ensemble_config,
        ).run(problem_factory)

    assert transition_count == 0


def test_nonqualified_result_writes_audit_files_but_not_pooled_outputs(
    tmp_path,
) -> None:
    chain_config, ensemble_config = _configs(save_pilot_samples=False)
    result = _result(
        NOT_QUALIFIED,
        chain_config,
        ensemble_config,
        save_pilot_samples=False,
    )

    pooled = write_mh_ensemble_result(result, tmp_path)

    assert pooled is None
    assert (tmp_path / "mcmc_diagnostics.tsv").is_file()
    assert (tmp_path / "chains" / "chain_001" / "lpm_dist_calibrated.txt").is_file()
    assert (tmp_path / "proposal_covariance.tsv").is_file()
    assert (tmp_path / "pilot" / "pilot_metadata.txt").is_file()
    assert not list((tmp_path / "pilot").glob("*_samples.tsv"))
    assert not (tmp_path / "lpm_dist_calibrated.txt").exists()
    assert not (tmp_path / "lpm_stats_calibrated.txt").exists()
    run_results = _read_key_values(tmp_path / "results_calibration.txt")
    assert run_results["pooling_written"] == "False"
    assert run_results["failed_diagnostic_count"] == "1"


def test_nonqualified_rerun_removes_stale_root_posterior_outputs(tmp_path) -> None:
    chain_config, ensemble_config = _configs(save_pilot_samples=False)
    qualified = _result(
        QUALIFIED,
        chain_config,
        ensemble_config,
        save_pilot_samples=False,
    )
    unqualified = _result(
        NOT_QUALIFIED,
        chain_config,
        ensemble_config,
        save_pilot_samples=False,
    )
    write_mh_ensemble_result(qualified, tmp_path)
    assert (tmp_path / "lpm_dist_calibrated.txt").is_file()

    pooled = write_mh_ensemble_result(unqualified, tmp_path)

    assert pooled is None
    assert not (tmp_path / "lpm_dist_calibrated.txt").exists()
    assert not (tmp_path / "lpm_stats_calibrated.txt").exists()
    assert not list(tmp_path.glob("lpm_histo_calibrated*.txt"))


def test_unqualified_pooling_is_bound_to_the_recorded_policy(tmp_path) -> None:
    chain_config, ensemble_config = _configs(
        save_pilot_samples=False,
        require_convergence=False,
    )
    result = _result(
        NOT_QUALIFIED,
        chain_config,
        ensemble_config,
        save_pilot_samples=False,
    )

    pooled = write_mh_ensemble_result(result, tmp_path)

    assert pooled is not None
    assert len(pooled.frame) == 16
    assert (tmp_path / "lpm_dist_calibrated.txt").is_file()
    run_results = _read_key_values(tmp_path / "results_calibration.txt")
    assert run_results["qualification_status"] == NOT_QUALIFIED
    assert run_results["pooling_written"] == "True"


def test_unavailable_diagnostics_still_write_chain_audit_files(tmp_path) -> None:
    chain_config, ensemble_config = _configs(save_pilot_samples=False)
    base = _result(
        NOT_QUALIFIED,
        chain_config,
        ensemble_config,
        save_pilot_samples=False,
    )
    result = replace(
        base,
        diagnostics=(),
        qualification_status=DIAGNOSTICS_UNAVAILABLE,
        diagnostics_message="non-finite derived quantity",
    )

    pooled = write_mh_ensemble_result(result, tmp_path)

    assert pooled is None
    assert (tmp_path / "chains" / "chain_001" / "lpm_dist_calibrated.txt").is_file()
    diagnostics = read_frame(tmp_path / "mcmc_diagnostics.tsv", index=False)
    assert diagnostics.empty
    run_results = _read_key_values(tmp_path / "results_calibration.txt")
    assert run_results["qualification_status"] == DIAGNOSTICS_UNAVAILABLE
    assert run_results["diagnostics_message"] == "non-finite derived quantity"


def test_atomic_key_value_write_preserves_an_existing_target_on_failure(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "metadata.txt"
    target.write_text("complete\told\n", encoding="utf-8")

    def fail_after_partial_write(path, _values) -> None:
        Path(path).write_text("partial", encoding="utf-8")
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(mh_results, "write_key_values", fail_after_partial_write)

    with pytest.raises(RuntimeError, match="serialization failed"):
        mh_results._write_key_values_atomic(target, {"complete": "new"})

    assert target.read_text(encoding="utf-8") == "complete\told\n"
    assert list(tmp_path.iterdir()) == [target]


def test_one_chain_cleanup_removes_only_multichain_artifacts(tmp_path) -> None:
    (tmp_path / "chains" / "chain_001").mkdir(parents=True)
    (tmp_path / "chains" / "chain_001" / "old.txt").write_text("old")
    (tmp_path / "pilot").mkdir()
    (tmp_path / "pilot" / "old.txt").write_text("old")
    (tmp_path / "initialization").mkdir()
    (tmp_path / "initialization" / "old.txt").write_text("old")
    for filename in (
        "ensemble_provenance.txt",
        "mcmc_diagnostics.tsv",
        "proposal_covariance.tsv",
    ):
        (tmp_path / filename).write_text("old")
    standard = tmp_path / "lpm_dist_calibrated.txt"
    standard.write_text("preserve until mono writer replaces it")

    clear_mh_ensemble_artifacts(tmp_path)

    assert not (tmp_path / "chains").exists()
    assert not (tmp_path / "pilot").exists()
    assert not (tmp_path / "initialization").exists()
    assert not (tmp_path / "ensemble_provenance.txt").exists()
    assert not (tmp_path / "mcmc_diagnostics.tsv").exists()
    assert not (tmp_path / "proposal_covariance.tsv").exists()
    assert standard.is_file()


def test_run_record_rejects_a_seed_plan_from_another_configuration() -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)
    other_config = MHEnsembleConfig(
        chains=ensemble_config.chains,
        master_seed=ensemble_config.master_seed + 1,
        initialization=ensemble_config.initialization,
        pilot=ensemble_config.pilot,
        diagnostics=ensemble_config.diagnostics,
    )

    with pytest.raises(ValueError, match="seed_plan"):
        replace(result, ensemble_config=other_config)


def test_run_record_rejects_a_configuration_with_the_wrong_chain_count() -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)
    wrong_config = MHEnsembleConfig(
        chains=3,
        master_seed=ensemble_config.master_seed,
        initialization=ensemble_config.initialization,
        pilot=ensemble_config.pilot,
        diagnostics=ensemble_config.diagnostics,
    )

    with pytest.raises(ValueError, match="chain count"):
        replace(result, ensemble_config=wrong_config)


def test_writer_rejects_mutated_chain_samples_before_creating_artifacts(
    tmp_path,
) -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)
    parameter = result.chains[0].samples.get_param_names()[0]
    result.chains[0].samples.frame.loc[0, parameter] = 999.0

    with pytest.raises(RuntimeError, match="changed after their diagnostic snapshot"):
        write_mh_ensemble_result(result, tmp_path)

    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_writer_rejects_mutated_pilot_before_creating_artifacts(tmp_path) -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)
    assert result.pilot is not None
    object.__setattr__(result.pilot, "covariance", np.array([[np.nan]]))

    with pytest.raises(RuntimeError, match="pilot result changed"):
        write_mh_ensemble_result(result, tmp_path)

    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_writer_accepts_only_the_configuration_bound_run_record(tmp_path) -> None:
    chain_config, ensemble_config = _configs()
    result = _result(QUALIFIED, chain_config, ensemble_config)

    with pytest.raises(TypeError):
        write_mh_ensemble_result(  # type: ignore[call-arg]
            result,
            tmp_path,
            chain_config,
            ensemble_config,
        )

    assert not tmp_path.exists() or not list(tmp_path.iterdir())
