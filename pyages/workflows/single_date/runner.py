# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Orchestration entry point for the installed single-date workflow."""

from __future__ import annotations

from pathlib import Path

from pyages.calibration.methods.mh import MHConvergenceError
from pyages.workflows.runtime.manifest import (
    promote_result_run,
    write_failure_manifest,
    write_result_manifest,
)
from pyages.workflows.single_date.calibration import (
    reachable_concentrations,
    run_calibrations,
)
from pyages.workflows.single_date.context import prepare_context, scientific_input_paths
from pyages.workflows.single_date.reporting import (
    render_summary,
    run_objective_analysis,
    write_concentration_outputs,
)


def _manifest_details(context, calibrations: list[str]) -> dict[str, object]:
    """Return the shared single-date terminal-state metadata."""
    return {
        "dataset": context.params.dataset_name,
        "dataset_year": context.params.dataset_year,
        "lpm": context.params.lpm_model_name,
        "calibrations": calibrations,
        "observation_error_policy": {
            "missing_error_rel": context.params.missing_error_rel,
            "transformations": context.observations.error_provenance,
        },
    }


def _run_id(context) -> str | None:
    """Return the isolated-run identity when the real context provides one."""
    result_run = getattr(context, "result_run", None)
    return getattr(result_run, "run_id", None)


def _promote_if_staged(context) -> Path:
    """Publish a real workflow context while keeping lightweight test doubles."""
    result_run = getattr(context, "result_run", None)
    if result_run is None:
        return context.output_directory
    return promote_result_run(result_run)


def run_single_date(params_path: str | Path, force_inline: bool = False) -> Path:
    """Run every enabled step from a single-date YAML configuration."""
    if params_path is None:
        raise ValueError("params_path is required for the launcher")
    context = prepare_context(params_path, force_inline=force_inline)
    try:
        context.observations.frame.to_csv(
            context.output_directory / "concentrations.txt",
            sep="\t",
            index=False,
        )
        reachable = reachable_concentrations(context)
        calibrated = run_calibrations(context)
        render_summary(context, reachable, calibrated)
        run_objective_analysis(context, calibrated)
        write_concentration_outputs(context)
        context.plots.finish()
        write_result_manifest(
            context.output_directory,
            workflow="single_date",
            config_path=context.config_path,
            input_paths=scientific_input_paths(context),
            details=_manifest_details(context, sorted(calibrated)),
            run_id=_run_id(context),
        )
        result_directory = _promote_if_staged(context)
    except MHConvergenceError as error:
        # ``run_calibrations`` executes Simplex first. Reaching its MH-specific
        # exception therefore proves that an enabled Simplex run completed.
        completed = ["Simplex"] if context.params.run_calibration_simplex else []
        details = _manifest_details(context, completed)
        details["calibrations_attempted"] = ["Metropolis_Hastings"]
        try:
            write_failure_manifest(
                context.output_directory,
                workflow="single_date",
                config_path=context.config_path,
                input_paths=scientific_input_paths(context),
                details=details,
                error=error,
                run_id=_run_id(context),
            )
            failure_directory = _promote_if_staged(context)
            error.add_note(f"Preserved result evidence: {failure_directory}")
        except Exception as manifest_error:
            error.add_note(f"Could not write failure manifest: {manifest_error}")
        context.plots.close_all()
        raise
    except BaseException:
        context.plots.close_all()
        raise
    return result_directory


__all__ = ["run_single_date"]
