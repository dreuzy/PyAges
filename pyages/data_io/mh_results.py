# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Auditable serialization of multi-chain Metropolis--Hastings results.

Production chains are always kept as separate files.  Pooling is an explicit
last step and therefore cannot hide failed or unavailable convergence
diagnostics.  Every individual file is replaced atomically so an interrupted
write never exposes a partially serialized table or metadata file.
"""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble_config import (
    MHEnsembleConfig,
    build_seed_plan,
)
from pyages.calibration.methods.mh.results import (
    QUALIFIED,
    MHEnsembleResult,
)
from pyages.calibration.outputs import write_key_values
from pyages.data_io.lpm_distribution import (
    write_distribution,
    write_frame,
    write_histograms,
    write_statistics,
)
from pyages.lpm.samples.table import LpmSampleTable


def _write_key_values_atomic(path: Path, values: dict[str, Any]) -> None:
    """Atomically replace one key/value file using the canonical serializer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            prefix=".pyages-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
        write_key_values(temporary_path, values)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _json(value: object) -> str:
    """Return stable, human-readable JSON for nested metadata values."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _chain_parameters_payload(
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    result: MHEnsembleResult,
) -> dict[str, Any]:
    """Build the root compatibility configuration and ensemble metadata."""
    initialization = ensemble_config.initialization
    pilot = ensemble_config.pilot
    diagnostics = ensemble_config.diagnostics
    proposal_kind = (
        "correlated" if result.pilot is not None else chain_config.proposal_kind
    )
    proposal_multiplier = (
        result.pilot.proposal_multiplier
        if result.pilot is not None
        else chain_config.proposal_multiplier
    )
    payload = {
        "method": "Metropolis_Hastings",
        "execution_mode": "multi_chain",
        "nstep": chain_config.nstep,
        "burn-in": chain_config.burn_in,
        "nskip": chain_config.nskip,
        "retained_sample_count": (
            chain_config.retained_sample_count() * ensemble_config.chains
        ),
        "retained_sample_count_per_chain": chain_config.retained_sample_count(),
        "prior_option": chain_config.prior_option,
        "prior_type": chain_config.prior_type,
        "prior_file": chain_config.prior_file,
        "likelihood_option": chain_config.likelihood,
        "proposal_kind": proposal_kind,
        "production_proposal_kind": proposal_kind,
        "proposal_multiplier": proposal_multiplier,
        "componentwise_source": chain_config.componentwise_source,
        "componentwise_fraction": chain_config.componentwise_fraction,
        "proposal_scales": _json(chain_config.proposal_scales),
        "configured_proposal_covariance": _json(chain_config.proposal_covariance),
        "proposal_covariance_file": (
            "proposal_covariance.tsv" if result.pilot is not None else ""
        ),
        "chain_count": ensemble_config.chains,
        "seed": ensemble_config.master_seed,
        "master_seed": ensemble_config.master_seed,
        "initialization_strategy": initialization.strategy,
        "initialization_max_attempts": initialization.max_attempts,
        "initialization_explicit_starts": _json(
            [dict(start) for start in initialization.explicit_starts]
            if initialization.explicit_starts is not None
            else None
        ),
        "pilot_enabled": pilot.enabled,
        "pilot_nstep": pilot.nstep,
        "pilot_burn-in": pilot.burn_in,
        "pilot_covariance_mode": pilot.covariance_mode,
        "pilot_relative_ridge": pilot.relative_ridge,
        "pilot_requested_proposal_multiplier": (
            "auto" if pilot.proposal_multiplier is None else pilot.proposal_multiplier
        ),
        "pilot_save_samples": pilot.save_samples,
        "diagnostics_max_rhat": diagnostics.max_rhat,
        "diagnostics_min_bulk_ess": diagnostics.min_bulk_ess,
        "diagnostics_min_tail_ess": diagnostics.min_tail_ess,
        "diagnostics_require_convergence": diagnostics.require_convergence,
    }
    payload.update(result.resolved_metadata)
    return payload


def _provenance_payload(
    result: MHEnsembleResult,
) -> dict[str, Any]:
    """Record replayable phase seeds and the realized ensemble status."""
    seed_plan = result.seed_plan
    payload: dict[str, Any] = {
        "format_version": 1,
        "method": "Metropolis_Hastings",
        "execution_mode": "multi_chain",
        "qualification_status": result.qualification_status,
        "diagnostics_message": result.diagnostics_message or "",
        "chain_count": len(result.chains),
        "master_seed": seed_plan.master_seed,
        "target_signature_version": result.target_signature_version,
        "target_sha256": result.target_sha256,
    }
    chains_by_id = sorted(result.chains, key=lambda chain: chain.chain_id)
    for index, chain in enumerate(chains_by_id, start=1):
        payload[f"chain_id_{index:03d}"] = chain.chain_id
        payload[f"initialization_seed_{index:03d}"] = seed_plan.initialization_seeds[
            index - 1
        ]
        payload[f"pilot_seed_{index:03d}"] = (
            seed_plan.pilot_seeds[index - 1] if result.pilot is not None else ""
        )
        payload[f"planned_pilot_seed_{index:03d}"] = seed_plan.pilot_seeds[index - 1]
        payload[f"production_seed_{index:03d}"] = chain.seed
        payload[f"planned_production_seed_{index:03d}"] = seed_plan.production_seeds[
            index - 1
        ]
    return payload


def _results_payload(
    result: MHEnsembleResult,
    pooled: LpmSampleTable | None,
) -> dict[str, Any]:
    """Build scalar run diagnostics for the root compatibility file."""
    rates = [chain.acceptance_rate for chain in result.chains]
    failed = sum(
        diagnostic.included_in_qualification and not diagnostic.qualified
        for diagnostic in result.diagnostics
    )
    informational_failed = sum(
        not diagnostic.included_in_qualification and not diagnostic.qualified
        for diagnostic in result.diagnostics
    )
    mean_rate = sum(rates) / len(rates)
    production_runtime = sum(chain.runtime_seconds for chain in result.chains)
    pilot_runtime = (
        sum(result.pilot.runtime_seconds)
        if result.pilot is not None and result.pilot.runtime_seconds is not None
        else 0.0
    )
    total_runtime = production_runtime + pilot_runtime
    return {
        "time_perform": total_runtime,
        "success_rate": mean_rate,
        "qualification_status": result.qualification_status,
        "diagnostics_message": result.diagnostics_message or "",
        "chain_count": len(result.chains),
        "retained_samples_per_chain": _json(
            [len(chain.samples.frame) for chain in result.chains]
        ),
        "pooled_sample_count": 0 if pooled is None else len(pooled.frame),
        "pooling_written": pooled is not None,
        "mean_success_rate": mean_rate,
        "minimum_success_rate": min(rates),
        "maximum_success_rate": max(rates),
        "production_runtime_sum_seconds": production_runtime,
        "pilot_runtime_sum_seconds": pilot_runtime,
        "total_runtime_seconds": total_runtime,
        "diagnostic_count": len(result.diagnostics),
        "failed_diagnostic_count": failed,
        "informational_failed_diagnostic_count": informational_failed,
    }


def _write_chains(result: MHEnsembleResult, output_directory: Path) -> None:
    """Write independent production draws and scalar chain provenance."""
    for chain in sorted(result.chains, key=lambda item: item.chain_id):
        chain_directory = output_directory / "chains" / f"chain_{chain.chain_id:03d}"
        write_distribution(
            chain.samples,
            chain_directory / "lpm_dist_calibrated.txt",
        )
        metadata: dict[str, Any] = {
            "chain_id": chain.chain_id,
            "seed": chain.seed,
            "retained_sample_count": len(chain.samples.frame),
            "success_rate": chain.acceptance_rate,
            "runtime_seconds": chain.runtime_seconds,
        }
        metadata.update(
            {f"initial_{name}": value for name, value in chain.initial_params.items()}
        )
        _write_key_values_atomic(
            chain_directory / "chain_metadata.txt",
            metadata,
        )


def _write_diagnostics(result: MHEnsembleResult, output_directory: Path) -> None:
    """Write one row per monitored parameter or derived quantity."""
    columns = [
        "parameter",
        "rhat",
        "bulk_ess",
        "tail_ess",
        "mcse_mean",
        "posterior_sd",
        "included_in_qualification",
        "qualified",
    ]
    frame = pd.DataFrame(
        (
            {
                "parameter": diagnostic.parameter,
                "rhat": diagnostic.rhat,
                "bulk_ess": diagnostic.bulk_ess,
                "tail_ess": diagnostic.tail_ess,
                "mcse_mean": diagnostic.mcse_mean,
                "posterior_sd": diagnostic.posterior_sd,
                "included_in_qualification": (diagnostic.included_in_qualification),
                "qualified": diagnostic.qualified,
            }
            for diagnostic in result.diagnostics
        ),
        columns=columns,
    )
    write_frame(frame, output_directory / "mcmc_diagnostics.tsv", index=False)


def _write_pilot(result: MHEnsembleResult, output_directory: Path) -> None:
    """Write learned covariance and optional retained pilot matrices."""
    pilot = result.pilot
    if pilot is None:
        return
    parameter_names = list(pilot.final_states[0])
    covariance = pd.DataFrame(
        pilot.covariance,
        index=parameter_names,
        columns=parameter_names,
    )
    covariance.index.name = "parameter"
    write_frame(
        covariance,
        output_directory / "proposal_covariance.tsv",
        index=True,
    )

    metadata: dict[str, Any] = {
        "proposal_multiplier": pilot.proposal_multiplier,
        "chain_count": len(pilot.final_states),
    }
    for index, (state, rate, retained_count) in enumerate(
        zip(
            pilot.final_states,
            pilot.acceptance_rates,
            pilot.retained_counts,
            strict=True,
        ),
        start=1,
    ):
        metadata[f"chain_{index:03d}_success_rate"] = rate
        metadata[f"chain_{index:03d}_retained_sample_count"] = retained_count
        if pilot.runtime_seconds is not None:
            metadata[f"chain_{index:03d}_runtime_seconds"] = pilot.runtime_seconds[
                index - 1
            ]
        if pilot.initial_states is not None:
            for name, value in pilot.initial_states[index - 1].items():
                metadata[f"chain_{index:03d}_initial_{name}"] = value
        for name, value in state.items():
            metadata[f"chain_{index:03d}_final_{name}"] = value
    _write_key_values_atomic(
        output_directory / "pilot" / "pilot_metadata.txt",
        metadata,
    )

    if pilot.samples is None:
        return
    for index, samples in enumerate(pilot.samples, start=1):
        frame = pd.DataFrame(samples, columns=parameter_names)
        write_frame(
            frame,
            output_directory / "pilot" / f"chain_{index:03d}_samples.tsv",
            index=False,
        )


def _validate_production_provenance(
    result: MHEnsembleResult,
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
) -> None:
    """Validate production counts and replayable chain seeds."""
    if len(result.chains) != ensemble_config.chains:
        raise ValueError("result chain count does not match the ensemble configuration")
    expected_draws = chain_config.retained_sample_count()
    if any(len(chain.samples.frame) != expected_draws for chain in result.chains):
        raise ValueError(
            "production retained counts do not match the chain configuration"
        )
    expected_seed_plan = build_seed_plan(ensemble_config)
    if result.seed_plan != expected_seed_plan:
        raise ValueError("result seed_plan does not match the ensemble configuration")
    planned_seeds = result.seed_plan.production_seeds
    recorded_seeds = tuple(
        chain.seed for chain in sorted(result.chains, key=lambda item: item.chain_id)
    )
    if recorded_seeds != planned_seeds:
        raise ValueError("production chain seeds do not match the ensemble seed plan")


def _validate_pilot_provenance(
    result: MHEnsembleResult,
    ensemble_config: MHEnsembleConfig,
) -> None:
    """Validate pilot presence, counts, and optional-sample policy."""
    if ensemble_config.pilot.enabled != (result.pilot is not None):
        raise ValueError(
            "pilot result presence does not match the ensemble configuration"
        )
    if result.pilot is None:
        return
    if result.pilot.runtime_seconds is None:
        raise ValueError("pilot runtimes are required for auditable serialization")
    if result.pilot is not None and (
        len(result.pilot.final_states) != ensemble_config.chains
    ):
        raise ValueError("pilot chain count does not match the ensemble configuration")
    expected_pilot_draws = (
        ensemble_config.pilot.nstep
        - math.floor(ensemble_config.pilot.burn_in * ensemble_config.pilot.nstep)
        - 1
    )
    if any(count != expected_pilot_draws for count in result.pilot.retained_counts):
        raise ValueError(
            "pilot retained counts do not match the ensemble configuration"
        )
    if ensemble_config.pilot.save_samples != (result.pilot.samples is not None):
        raise ValueError(
            "saved pilot samples do not match pilot.save_samples configuration"
        )


def _validate_arguments(
    result: MHEnsembleResult,
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    allow_unqualified_pooling: bool,
) -> None:
    """Reject inconsistent provenance before creating any output."""
    if not isinstance(result, MHEnsembleResult):
        raise TypeError("result must be an MHEnsembleResult")
    if not isinstance(chain_config, MHConfig):
        raise TypeError("chain_config must be an MHConfig")
    if not isinstance(ensemble_config, MHEnsembleConfig):
        raise TypeError("ensemble_config must be an MHEnsembleConfig")
    if not isinstance(allow_unqualified_pooling, bool):
        raise TypeError("allow_unqualified_pooling must be a boolean")
    _validate_production_provenance(result, chain_config, ensemble_config)
    _validate_pilot_provenance(result, ensemble_config)


def clear_mh_ensemble_artifacts(output_directory: str | Path) -> None:
    """Remove multi-chain-only artifacts before a one-chain rerun.

    Standard root posterior files are intentionally preserved because the
    one-chain writer replaces them. Only directories and files exclusively
    owned by the ensemble implementation are removed.
    """
    destination = Path(output_directory)
    for directory_name in ("chains", "initialization", "pilot"):
        directory = destination / directory_name
        if directory.is_symlink() or directory.is_file():
            directory.unlink()
        elif directory.is_dir():
            shutil.rmtree(directory)
    for filename in (
        "ensemble_provenance.txt",
        "mcmc_diagnostics.tsv",
        "proposal_covariance.tsv",
    ):
        (destination / filename).unlink(missing_ok=True)


def _clear_previous_ensemble_artifacts(output_directory: Path) -> None:
    """Remove all files and directories owned by a prior ensemble run."""
    clear_mh_ensemble_artifacts(output_directory)
    for filename in (
        "lpm_dist_calibrated.txt",
        "lpm_stats_calibrated.txt",
        "parameters_calibration.txt",
        "results_calibration.txt",
    ):
        (output_directory / filename).unlink(missing_ok=True)
    for histogram in output_directory.glob("lpm_histo_calibrated*.txt"):
        if histogram.is_file() or histogram.is_symlink():
            histogram.unlink()


def write_mh_ensemble_result(
    result: MHEnsembleResult,
    output_directory: str | Path,
    chain_config: MHConfig,
    ensemble_config: MHEnsembleConfig,
    *,
    allow_unqualified_pooling: bool = False,
) -> LpmSampleTable | None:
    """Serialize a complete MH ensemble without premature chain pooling.

    Chain samples, their metadata, convergence diagnostics, seed provenance,
    and pilot information are written for every result status.  The standard
    root distribution, histograms, and statistics are produced only for a
    qualified ensemble, unless exploratory pooling is explicitly enabled with
    ``allow_unqualified_pooling=True``.

    Returns
    -------
    LpmSampleTable or None
        A newly pooled sample table when root posterior outputs were written;
        otherwise ``None``.  Individual chain tables are never mutated.
    """
    _validate_arguments(
        result,
        chain_config,
        ensemble_config,
        allow_unqualified_pooling,
    )
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    _clear_previous_ensemble_artifacts(destination)

    _write_chains(result, destination)
    _write_diagnostics(result, destination)
    _write_pilot(result, destination)
    _write_key_values_atomic(
        destination / "ensemble_provenance.txt",
        _provenance_payload(result),
    )
    _write_key_values_atomic(
        destination / "parameters_calibration.txt",
        _chain_parameters_payload(chain_config, ensemble_config, result),
    )

    pooled: LpmSampleTable | None = None
    if result.qualification_status == QUALIFIED or allow_unqualified_pooling:
        pooled = result.pooled_samples(require_qualified=not allow_unqualified_pooling)
        write_distribution(pooled, destination / "lpm_dist_calibrated.txt")
        write_histograms(pooled, destination / "lpm_histo_calibrated.txt")
        write_statistics(pooled, destination / "lpm_stats_calibrated.txt")

    _write_key_values_atomic(
        destination / "results_calibration.txt",
        _results_payload(result, pooled),
    )
    return pooled


__all__ = ["clear_mh_ensemble_artifacts", "write_mh_ensemble_result"]
