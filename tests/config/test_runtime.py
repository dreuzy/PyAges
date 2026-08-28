# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Deterministic contracts for display and runtime helpers."""

from __future__ import annotations

import numpy as np
import pytest

from pyages.config import runtime


def test_subdivide_interval_includes_endpoints_and_rejects_invalid_count() -> None:
    assert runtime.subdivide_interval(2.0, 5.0, 3).tolist() == [2.0, 3.0, 4.0, 5.0]
    assert runtime.subdivide_interval(2.0, 5.0, np.int64(3)).tolist() == [
        2.0,
        3.0,
        4.0,
        5.0,
    ]

    for invalid_count in (0, -1, 2.5, True, "3"):
        with pytest.raises(ValueError, match="integer >= 1"):
            runtime.subdivide_interval(0.0, 1.0, invalid_count)


def test_display_options_returns_no_path_when_figure_saving_is_disabled(
    tmp_path,
) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    assert display.figure_path("diagnostic.png") is None


def test_display_options_builds_method_figure_path(tmp_path) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    display.figure_save = True

    output = display.figure_path("diagnostic.png", method="calibration")

    assert output == tmp_path / "calibration" / "diagnostic.png"


def test_display_options_requires_directory_when_saving() -> None:
    display = runtime.DisplayOptions()
    display.figure_save = True

    with pytest.raises(ValueError, match="directory must be configured"):
        display.figure_path("diagnostic.png")


def test_simulation_timer_initializes_once_and_reports_remaining_time(
    monkeypatch, capsys
) -> None:
    clock = iter([100.0, 100.0, 3700.0, 7300.0])
    monkeypatch.setattr(runtime.time, "time", lambda: next(clock))
    timer = runtime.SimulationTimer(nsim=2)

    timer.initialize(3)
    timer.initialize(99)
    timer.actualize(2)
    timer.actualize(4)

    output = capsys.readouterr().out
    assert timer.simul_total == 6
    assert timer.simul_current == 6
    assert "time elapsed = 1.0000 h | time remaining = 2.0000 h" in output
    assert "time elapsed = 2.0000 h | time remaining = 0.0000 h" in output
