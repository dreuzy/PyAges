"""Figures used by installed PyAge workflows."""

from pyage.workflows.plots.common import apply_example_style
from pyage.workflows.plots.model_space import plot_single_date_model_space
from pyage.workflows.plots.objective import (
    plot_objective_solution_map,
    plot_objective_summary,
)
from pyage.workflows.plots.observations import plot_observations_overview
from pyage.workflows.plots.parameters import (
    plot_parameter_distribution_comparison,
    plot_parameter_summary,
)
from pyage.workflows.plots.temporal import (
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
