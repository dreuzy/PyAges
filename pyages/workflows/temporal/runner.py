# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file orchestrates temporal calibration from configuration to publication.

"""Execute every case and model requested by a temporal workflow configuration.

The runner prepares shared inputs, partitions observations into their configured
time cases, and calibrates each requested LPM. Optional observation overviews and
per-model diagnostic figures are written inside the private result stage as the
cases complete.

A terminal manifest records success or an accepted convergence failure before
the stage is atomically published. The return value points to the published root,
or directly to its sole case directory when the workflow produced only one case.
"""

from __future__ import annotations

from pathlib import Path

from pyages.calibration.methods.mh import MHConvergenceError
from pyages.concentrations import Concentrations
from pyages.config.models import TemporalCalibrationCfg, TemporalFiguresCfg
from pyages.config.paths import result_subdirectory
from pyages.reporting.plots import plot_observations_overview
from pyages.workflows.runtime import (
    promote_result_run,
    write_failure_manifest,
    write_result_manifest,
)
from pyages.workflows.temporal.calibration import run_model_calibration
from pyages.workflows.temporal.cases import build_case_frames
from pyages.workflows.temporal.context import prepare_context, scientific_input_paths


def _run_temporal_cases(
    observations: Concentrations,
    mode_root: Path,
    mode: str,
    models: list[str],
    lpm_directory: Path,
    calibration_cfg: TemporalCalibrationCfg,
    figures_cfg: TemporalFiguresCfg,
    *,
    written_case_directories: list[Path] | None = None,
) -> list[Path]:
    """Execute every observation-subset and LPM combination."""
    if written_case_directories is None:
        written_case_directories = []
    for date_label, frame in build_case_frames(observations, mode):
        case_data = Concentrations.from_dataframe(frame)
        case_directory = result_subdirectory(mode_root, date_label)
        written_case_directories.append(case_directory)
        if figures_cfg.temporal or figures_cfg.distributions:
            figure = plot_observations_overview(
                case_data,
                filename=case_directory / "00_observations_overview.png",
                title="Observed concentrations before calibration",
            )
            import matplotlib.pyplot as plt

            plt.close(figure)
        for lpm_type in models:
            run_model_calibration(
                observations=case_data,
                lpm_type=lpm_type,
                output_directory=result_subdirectory(case_directory, lpm_type),
                lpm_directory=lpm_directory,
                calibration_cfg=calibration_cfg,
                figures_cfg=figures_cfg,
            )
    return written_case_directories


def _manifest_details(context, case_directories: list[Path]) -> dict[str, object]:
    """Return the shared temporal terminal-state metadata."""
    return {
        "dataset": context.dataset_path.name,
        "mode": context.mode,
        "lpms": context.models,
        "observation_error_policy": {
            "error_rel": context.params.dataset.error_rel,
            "missing_error_rel": context.params.dataset.missing_error_rel,
            "transformations": context.observations.error_provenance,
        },
        "case_directories": [
            path.relative_to(context.output_directory).as_posix()
            for path in case_directories
        ],
    }


def run_temporal(params_path: str | Path) -> Path:
    """Execute, seal, and publish all cases in a temporal MH workflow.

    Shared configuration and observations are prepared once, then partitioned
    into the requested temporal cases. Every configured LPM is calibrated inside
    its case directory, with optional figures written into the same private
    result stage. The list of completed case directories becomes part of terminal
    provenance.

    On convergence failure, a sealed failure result containing work completed so
    far is published when possible and the original exception is re-raised with
    its location attached. On success, the whole stage is sealed and atomically
    promoted. The function returns the published root for multiple cases, or the
    published case directory itself when exactly one case was produced.
    """
    context = prepare_context(params_path)
    context.observations.frame.to_csv(
        context.output_directory / "concentrations.txt",
        sep="\t",
        index=False,
    )
    written_case_directories: list[Path] = []
    # Track completed cases incrementally so a convergence-failure manifest can
    # distinguish preserved results from cases that were never reached.
    try:
        written_case_directories = _run_temporal_cases(
            context.observations,
            context.output_directory,
            context.mode,
            context.models,
            context.lpm_directory,
            context.params.calibration,
            context.params.figures,
            written_case_directories=written_case_directories,
        )
    except MHConvergenceError as error:
        try:
            write_failure_manifest(
                context.output_directory,
                workflow="temporal",
                config_path=context.config_path,
                input_paths=scientific_input_paths(context),
                details=_manifest_details(context, written_case_directories),
                error=error,
                run_id=context.result_run.run_id,
            )
            failure_directory = promote_result_run(context.result_run)
            error.add_note(f"Preserved result evidence: {failure_directory}")
        except Exception as manifest_error:
            error.add_note(f"Could not write failure manifest: {manifest_error}")
        raise
    # Publication occurs only after the root manifest commits every case written
    # by the loop; staged paths are translated to their public equivalents below.
    write_result_manifest(
        context.output_directory,
        workflow="temporal",
        config_path=context.config_path,
        input_paths=scientific_input_paths(context),
        details=_manifest_details(context, written_case_directories),
        run_id=context.result_run.run_id,
    )
    result_directory = promote_result_run(context.result_run)

    if len(written_case_directories) == 1:
        relative_case = written_case_directories[0].relative_to(
            context.output_directory
        )
        return result_directory / relative_case
    return result_directory


__all__ = ["run_temporal"]
