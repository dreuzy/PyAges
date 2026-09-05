# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file re-exports the supported reporting plot functions from one stable
# namespace. Workflows pass observations, objective grids, or posterior samples
# to these functions and receive Matplotlib figures that can optionally be saved.

"""Figures used by installed PyAges reporting and workflows."""

from pyages.reporting.plots._common import apply_example_style
from pyages.reporting.plots.model_space import plot_single_date_model_space
from pyages.reporting.plots.objective_solution import plot_objective_solution_map
from pyages.reporting.plots.objective_summary import plot_objective_summary
from pyages.reporting.plots.observations import plot_observations_overview
from pyages.reporting.plots.parameters import (
    plot_parameter_distribution_comparison,
    plot_parameter_summary,
)
from pyages.reporting.plots.temporal import (
    plot_temporal_fit_comparison,
    plot_temporal_fit_summary,
)

__all__ = [
    "apply_example_style",
    "plot_objective_solution_map",
    "plot_objective_summary",
    "plot_observations_overview",
    "plot_parameter_distribution_comparison",
    "plot_parameter_summary",
    "plot_single_date_model_space",
    "plot_temporal_fit_comparison",
    "plot_temporal_fit_summary",
]
