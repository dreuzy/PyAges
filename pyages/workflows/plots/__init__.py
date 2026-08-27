# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Figures used by installed PyAges workflows."""

from pyages.workflows.plots.common import apply_example_style
from pyages.workflows.plots.model_space import plot_single_date_model_space
from pyages.workflows.plots.objective import (
    plot_objective_solution_map,
    plot_objective_summary,
)
from pyages.workflows.plots.observations import plot_observations_overview
from pyages.workflows.plots.parameters import (
    plot_parameter_distribution_comparison,
    plot_parameter_summary,
)
from pyages.workflows.plots.temporal import (
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
