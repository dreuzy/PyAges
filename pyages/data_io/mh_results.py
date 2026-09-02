# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file writes pilot, production-chain, diagnostic, and provenance artifacts
# while keeping chains separate until convergence permits an explicit pool.
# Each table or metadata file is replaced atomically, and a failed qualification
# still retains the individual chains needed to diagnose the run.

"""Auditable serialization of multi-chain Metropolis--Hastings results.

Production chains are always kept as separate files.  Pooling is an explicit
last step and therefore cannot hide failed or unavailable convergence
diagnostics.  Every individual file is replaced atomically so an interrupted
write never exposes a partially serialized table or metadata file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd

from pyages.calibration.methods.mh.results import (
    QUALIFIED,
    MHRunRecord,
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
    record: MHRunRecord,
) -> dict[str, Any]:
    """Build the root compatibility configuration and ensemble metadata."""
    chain_config = record.chain_config
    ensemble_config = record.ensemble_config
    initialization = ensemble_config.initialization
    pilot = ensemble_config.pilot
    diagnostics = ensemble_config.diagnostics
    proposal_kind = (
        "correlated" if record.pilot is not None else chain_config.proposal_kind
    )
    proposal_multiplier = (
        record.pilot.proposal_multiplier
        if record.pilot is not None
        else chain_config.proposal_multiplier
    )
    payload = {
        "method": "Metropolis_Hastings",
        "execution_mode": "multi_chain",
        "nstep": chain_config.nstep,
        "burn_in": chain_config.burn_in,
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
            "proposal_covariance.tsv" if record.pilot is not None else ""
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
        "pilot_burn_in": pilot.burn_in,
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
    payload.update(record.resolved_metadata)
    return payload


def _provenance_payload(
    record: MHRunRecord,
) -> dict[str, Any]:
    """Record replayable phase seeds and the realized ensemble status."""
    seed_plan = record.seed_plan
    payload: dict[str, Any] = {
        "format_version": 1,
        "method": "Metropolis_Hastings",
        "execution_mode": "multi_chain",
        "qualification_status": record.qualification_status,
        "diagnostics_message": record.diagnostics_message or "",
        "chain_count": len(record.chains),
        "master_seed": seed_plan.master_seed,
        "target_signature_version": record.target_signature_version,
        "target_sha256": record.target_sha256,
    }
    chains_by_id = sorted(record.chains, key=lambda chain: chain.chain_id)
    for index, chain in enumerate(chains_by_id, start=1):
        payload[f"chain_id_{index:03d}"] = chain.chain_id
        payload[f"initialization_seed_{index:03d}"] = seed_plan.initialization_seeds[
            index - 1
        ]
        payload[f"pilot_seed_{index:03d}"] = (
            seed_plan.pilot_seeds[index - 1] if record.pilot is not None else ""
        )
        payload[f"planned_pilot_seed_{index:03d}"] = seed_plan.pilot_seeds[index - 1]
        payload[f"production_seed_{index:03d}"] = chain.seed
    return payload


def _results_payload(
    record: MHRunRecord,
    pooled: LpmSampleTable | None,
) -> dict[str, Any]:
    """Build scalar run diagnostics for the root compatibility file."""
    rates = [chain.acceptance_rate for chain in record.chains]
    failed = sum(
        diagnostic.included_in_qualification and not diagnostic.qualified
        for diagnostic in record.diagnostics
    )
    informational_failed = sum(
        not diagnostic.included_in_qualification and not diagnostic.qualified
        for diagnostic in record.diagnostics
    )
    mean_rate = sum(rates) / len(rates)
    production_runtime = sum(chain.runtime_seconds for chain in record.chains)
    pilot_runtime = (
        sum(record.pilot.runtime_seconds)
        if record.pilot is not None and record.pilot.runtime_seconds is not None
        else 0.0
    )
    total_runtime = production_runtime + pilot_runtime
    return {
        "time_perform": total_runtime,
        "success_rate": mean_rate,
        "qualification_status": record.qualification_status,
        "diagnostics_message": record.diagnostics_message or "",
        "chain_count": len(record.chains),
        "retained_samples_per_chain": _json(
            [len(chain.samples.frame) for chain in record.chains]
        ),
        "pooled_sample_count": 0 if pooled is None else len(pooled.frame),
        "pooling_written": pooled is not None,
        "mean_acceptance_rate": mean_rate,
        "minimum_acceptance_rate": min(rates),
        "maximum_acceptance_rate": max(rates),
        "production_runtime_sum_seconds": production_runtime,
        "pilot_runtime_sum_seconds": pilot_runtime,
        "total_runtime_seconds": total_runtime,
        "diagnostic_count": len(record.diagnostics),
        "failed_diagnostic_count": failed,
        "informational_failed_diagnostic_count": informational_failed,
    }


def _write_chains(record: MHRunRecord, output_directory: Path) -> None:
    """Write independent production draws and scalar chain provenance."""
    for chain in sorted(record.chains, key=lambda item: item.chain_id):
        chain_directory = output_directory / "chains" / f"chain_{chain.chain_id:03d}"
        write_distribution(
            chain.samples,
            chain_directory / "lpm_dist_calibrated.txt",
        )
        metadata: dict[str, Any] = {
            "chain_id": chain.chain_id,
            "seed": chain.seed,
            "retained_sample_count": len(chain.samples.frame),
            "acceptance_rate": chain.acceptance_rate,
            "runtime_seconds": chain.runtime_seconds,
        }
        metadata.update(
            {f"initial_{name}": value for name, value in chain.initial_params.items()}
        )
        _write_key_values_atomic(
            chain_directory / "chain_metadata.txt",
            metadata,
        )


def _write_diagnostics(record: MHRunRecord, output_directory: Path) -> None:
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
            for diagnostic in record.diagnostics
        ),
        columns=columns,
    )
    write_frame(frame, output_directory / "mcmc_diagnostics.tsv", index=False)


def _write_pilot(record: MHRunRecord, output_directory: Path) -> None:
    """Write learned covariance and optional retained pilot matrices."""
    pilot = record.pilot
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
        metadata[f"chain_{index:03d}_acceptance_rate"] = rate
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


def _validate_record(record: MHRunRecord) -> None:
    """Reject mutated or internally inconsistent provenance before output."""
    if not isinstance(record, MHRunRecord):
        raise TypeError("record must be an MHRunRecord")
    record.validate_integrity()


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
    record: MHRunRecord,
    output_directory: str | Path,
) -> LpmSampleTable | None:
    """Serialize a complete MH ensemble without premature chain pooling.

    Chain samples, their metadata, convergence diagnostics, seed provenance,
    and pilot information are written for every result status.  The standard
    root distribution, histograms, and statistics are produced only for a
    qualified ensemble. Exploratory pooling is enabled only by the immutable
    run configuration's ``diagnostics.require_convergence=False`` policy.

    Returns
    -------
    LpmSampleTable or None
        A newly pooled sample table when root posterior outputs were written;
        otherwise ``None``.  Individual chain tables are never mutated.

    """
    _validate_record(record)
    ensemble_config = record.ensemble_config
    allow_unqualified_pooling = not ensemble_config.diagnostics.require_convergence
    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    _clear_previous_ensemble_artifacts(destination)

    _write_chains(record, destination)
    _write_diagnostics(record, destination)
    _write_pilot(record, destination)
    _write_key_values_atomic(
        destination / "ensemble_provenance.txt",
        _provenance_payload(record),
    )
    _write_key_values_atomic(
        destination / "parameters_calibration.txt",
        _chain_parameters_payload(record),
    )

    pooled: LpmSampleTable | None = None
    if record.qualification_status == QUALIFIED or allow_unqualified_pooling:
        pooled = record.pooled_samples(require_qualified=not allow_unqualified_pooling)
        write_distribution(pooled, destination / "lpm_dist_calibrated.txt")
        write_histograms(pooled, destination / "lpm_histo_calibrated.txt")
        write_statistics(pooled, destination / "lpm_stats_calibrated.txt")

    _write_key_values_atomic(
        destination / "results_calibration.txt",
        _results_payload(record, pooled),
    )
    return pooled


__all__ = ["clear_mh_ensemble_artifacts", "write_mh_ensemble_result"]
