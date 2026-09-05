# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file produces reports and numerical exports for a single-date run.

"""Turn single-date reachability and calibration results into staged outputs.

The reporting steps combine observations, reachable concentrations, and
posterior samples into model-space and parameter figures. When requested, they
also evaluate an objective grid that shows how fit quality varies across the
configured parameter domain.

Calibrated sample tables and their predicted tracer histories are exported
beside the figures for each method. This module consumes completed calculations;
it does not decide run status or publish the result directory.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pyages.calibration.exploration.systematic import SystematicSampling
from pyages.config.models import LauncherConfig
from pyages.lpm.factory import build_lpm
from pyages.lpm.samples import LpmSampleTable
from pyages.reporting.chronicles import export_concentration_chronicles
from pyages.workflows.single_date.context import SingleDateContext


def case_label(params: LauncherConfig) -> str:
    """Return the explicit case label or a readable dataset filename stem."""
    return params.dataset.label or Path(params.dataset.name).stem.replace("_", " ")


def render_summary(
    context: SingleDateContext,
    reachable: pd.DataFrame | None,
    calibrated: dict[str, LpmSampleTable],
) -> None:
    """Render model-space and parameter summaries for calibrated methods."""
    if not calibrated:
        return
    from pyages.reporting.plots import (
        plot_parameter_summary,
        plot_single_date_model_space,
    )

    label = case_label(context.params)
    if reachable is not None:
        figure = plot_single_date_model_space(
            context.observations,
            reachable_frame=reachable,
            posterior_results=calibrated,
            filename=context.output_directory / "01_data_model_space.png",
            title=f"{label}: observations, reachable space and calibrated models",
        )
        context.plots.show()
        context.plots.close(figure)
    parameter_names = next(iter(calibrated.values())).get_param_names()
    figure = plot_parameter_summary(
        calibrated,
        param_names=parameter_names,
        filename=context.output_directory / "02_parameter_summary.png",
        title=f"{label}: parameter distributions",
    )
    context.plots.show()
    context.plots.close(figure)


def run_objective_analysis(
    context: SingleDateContext,
    calibrated: dict[str, LpmSampleTable],
) -> None:
    """Evaluate, serialize, and plot the configured objective-function grid."""
    if not context.params.run.objective_function:
        return
    from pyages.reporting.plots import plot_objective_summary

    sampling = SystematicSampling(
        context.params.lpm.model_name,
        context.observations.observation_tracer_names(),
        date=context.observations.frame["date"],
        observations=context.observations,
        sample_count=context.params.objective_function.nmodels,
        display_options=context.live_display,
        explore_objective=True,
        explore_reachable=False,
        lpm_directory=context.params.lpm.data_directory,
        tracer_data_directory=context.params.tracers.data_directory,
    )
    sampling.compute_concentrations()
    sampling.objective_function_build()
    objective = sampling.objective_function_frame()
    objective.to_csv(
        context.output_directory / "objective_function_grid.txt",
        sep="\t",
        index=False,
    )
    figure = plot_objective_summary(
        objective_frame=objective,
        posterior_results=calibrated,
        param_names=sampling.parameter_names(),
        filename=context.output_directory / "03_objective_summary.png",
        title=f"{case_label(context.params)}: objective landscape and parameters",
    )
    context.plots.show()
    context.plots.close(figure)


def write_concentration_outputs(context: SingleDateContext) -> None:
    """Write posterior distribution tables and concentration chronicles."""
    model = build_lpm(
        context.params.lpm.model_name,
        directory_lpm=context.params.lpm.data_directory,
    )
    export_concentration_chronicles(
        [context.output_directory],
        model,
        context.saved_display,
        tracer_data_dir=context.params.tracers.data_directory,
    )


__all__ = [
    "case_label",
    "render_summary",
    "run_objective_analysis",
    "write_concentration_outputs",
]
