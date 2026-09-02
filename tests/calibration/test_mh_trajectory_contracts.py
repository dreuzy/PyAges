# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Boundary and plotting contracts for retained MH trajectories."""

import matplotlib.pyplot as plt
import pytest

from pyages.calibration.methods.mh.trajectory import MHTrajectory


@pytest.mark.parametrize("nstep", [True, -1, 1.5])
def test_trajectory_rejects_invalid_capacity(nstep) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        MHTrajectory(["mu"], nstep)


@pytest.mark.parametrize("params", [[], [""], ["mu", "mu"]])
def test_trajectory_rejects_invalid_parameter_names(params) -> None:
    with pytest.raises(ValueError, match="unique non-empty"):
        MHTrajectory(params, 1)


def test_trajectory_validates_updates_and_resize() -> None:
    trajectory = MHTrajectory(["mu"], 2)
    with pytest.raises(IndexError):
        trajectory.update(2, [1.0], 0.0, accepted=True)
    with pytest.raises(ValueError, match="parameter count"):
        trajectory.update(0, [1.0, 2.0], 0.0, accepted=True)
    with pytest.raises(TypeError, match="accepted"):
        trajectory.update(0, [1.0], 0.0, accepted=1)
    with pytest.raises(ValueError, match="finite"):
        trajectory.update(0, [float("nan")], 0.0, accepted=True)
    with pytest.raises(ValueError, match="preallocated"):
        trajectory.resize(3)


def test_trajectory_plot_creates_directory_saves_png_and_closes(tmp_path) -> None:
    trajectory = MHTrajectory(["mu"], 1)
    trajectory.update(0, [10.0], -1.0, accepted=True)
    output = tmp_path / "nested" / "trajectory"

    trajectory.plot(output)

    assert (output / "MH_trajectory_mu.png").is_file()
    assert (output / "MH_trajectory_-log_posterior.png").is_file()
    assert (output / "MH_trajectory_incrementation.png").is_file()
    assert not plt.get_fignums()
