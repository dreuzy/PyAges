"""Compatibility facade for workflow plotting functions.

New code may import from :mod:`pyage.workflows.plots`; this module keeps the
historical import path used by examples and site workflows.
"""

from pyage.workflows.plots import (
    apply_example_style,
    plot_objective_solution_map,
    plot_objective_summary,
    plot_observations_overview,
    plot_parameter_distribution_comparison,
    plot_parameter_summary,
    plot_single_date_model_space,
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
