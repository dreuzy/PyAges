# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regression tests for Metropolis-Hastings trajectory display."""

from types import SimpleNamespace
from unittest.mock import Mock

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig


def test_trajectory_plot_uses_problem_display_directory(tmp_path):
    """Trajectory plots use the display options owned by the problem."""
    sampler = MetropolisHastings(config=MHConfig(display_traj=True))
    sampler._problem = SimpleNamespace(
        display_options=SimpleNamespace(directory=tmp_path)
    )
    trajectory = Mock()

    sampler._finalize_trajectory(trajectory, 3)  # noqa: SLF001

    trajectory.resize.assert_called_once_with(3)
    trajectory.plot.assert_called_once_with(tmp_path)
