"""Regression tests for Metropolis-Hastings trajectory display."""

from types import SimpleNamespace
from unittest.mock import Mock

from pyage.calibration.methods.metropolis_hastings import MetropolisHastings
from pyage.calibration.methods.trajectory import MHConfig, TrajOptions


def test_trajectory_plot_uses_problem_display_directory(tmp_path):
    """Trajectory plots use the display options owned by the problem."""
    sampler = MetropolisHastings(config=MHConfig())
    sampler._problem = SimpleNamespace(
        display_options=SimpleNamespace(directory=tmp_path)
    )
    trajectory = Mock()

    sampler._MetropolisHastings__finalize_trajectory(
        trajectory,
        3,
        TrajOptions(monitor=True, display=True, text=False),
    )

    trajectory.resize.assert_called_once_with(3)
    trajectory.plot.assert_called_once_with(tmp_path)
    trajectory.check.assert_not_called()
