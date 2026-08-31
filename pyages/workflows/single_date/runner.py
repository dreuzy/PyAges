# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Orchestration entry point for the installed single-date workflow."""

from __future__ import annotations

from pathlib import Path

from pyages.calibration.methods.mh import MHConvergenceError
from pyages.workflows.runtime.manifest import (
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
        )
    except MHConvergenceError as error:
        details = _manifest_details(context, [])
        details["calibrations_attempted"] = ["Metropolis_Hastings"]
        try:
            write_failure_manifest(
                context.output_directory,
                workflow="single_date",
                config_path=context.config_path,
                input_paths=scientific_input_paths(context),
                details=details,
                error=error,
            )
        except Exception as manifest_error:
            error.add_note(f"Could not write failure manifest: {manifest_error}")
        context.plots.close_all()
        raise
    except BaseException:
        context.plots.close_all()
        raise
    return context.output_directory


__all__ = ["run_single_date"]
