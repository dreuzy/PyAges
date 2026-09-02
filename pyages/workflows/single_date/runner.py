# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file orchestrates an installed single-date workflow from start to publication.

"""Execute the complete single-date workflow described by one YAML file.

The runner prepares validated inputs, samples reachable model space, executes
the requested calibrations, renders reports, and exports predicted concentration
histories in dependency order. Individual steps operate inside the private stage
created by the workflow context.

At the terminal boundary, the runner records either successful provenance or an
MH convergence failure, then atomically publishes the sealed stage. Unexpected
exceptions retain failure evidence and are propagated to the caller.
"""

from __future__ import annotations

from pathlib import Path

from pyages.calibration.methods.mh import MHConvergenceError
from pyages.workflows.runtime import (
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


def run_single_date(params_path: str | Path, force_inline: bool = False) -> Path:
    """Execute, seal, and publish every enabled single-date workflow step.

    The configuration and observations are validated before a private result
    stage is created. Inside that stage the runner saves prepared observations,
    samples reachable concentrations, executes enabled calibrations, renders
    reports, and exports modeled tracer histories. A successful terminal manifest
    is written and sealed before atomic promotion to the public result path.

    ``force_inline`` requests the notebook plotting backend during context
    preparation. The returned path is the published result directory. If MH
    convergence fails, available evidence receives a failure manifest and is
    published when possible; the original ``MHConvergenceError`` is then raised
    with the evidence location attached as a note. Other exceptions close open
    figures and propagate without publishing an unsealed stage.
    """
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
        # Seal provenance only after every enabled scientific and reporting step
        # has completed; promotion accepts no later artifact mutation.
        write_result_manifest(
            context.output_directory,
            workflow="single_date",
            config_path=context.config_path,
            input_paths=scientific_input_paths(context),
            details=_manifest_details(context, sorted(calibrated)),
            run_id=context.result_run.run_id,
        )
        result_directory = promote_result_run(context.result_run)
    except MHConvergenceError as error:
        # ``run_calibrations`` executes Simplex first. Reaching its MH-specific
        # exception therefore proves that an enabled Simplex run completed.
        completed = ["Simplex"] if context.params.run_calibration_simplex else []
        details = _manifest_details(context, completed)
        details["calibrations_attempted"] = ["Metropolis_Hastings"]
        # A convergence failure is a terminal scientific result rather than an
        # infrastructure crash, so preserve its completed evidence when possible.
        try:
            write_failure_manifest(
                context.output_directory,
                workflow="single_date",
                config_path=context.config_path,
                input_paths=scientific_input_paths(context),
                details=details,
                error=error,
                run_id=context.result_run.run_id,
            )
            failure_directory = promote_result_run(context.result_run)
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
