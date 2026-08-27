# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Deterministic contracts for display and runtime helpers."""

from __future__ import annotations

from unittest.mock import Mock

import matplotlib
import pytest

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

from pyages.config import runtime


def test_subdivide_interval_includes_endpoints_and_rejects_invalid_count() -> None:
    assert runtime.subdivide_interval(2.0, 5.0, 3).tolist() == [2.0, 3.0, 4.0, 5.0]

    with pytest.raises(ValueError, match="must be positive"):
        runtime.subdivide_interval(0.0, 1.0, 0)


def test_display_options_save_remove_legend_and_close(tmp_path) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    display.figure_close = True
    figure, axis = plt.subplots()
    axis.plot([0.0, 1.0], [1.0, 2.0], label="model")
    axis.legend()

    display.save_and_close(
        figure,
        "summary.png",
        method="calibration",
        dpi=72,
        ax=axis,
        with_legend=False,
    )

    assert (tmp_path / "calibration" / "summary.png").is_file()
    assert axis.get_legend() is None
    assert not plt.fignum_exists(figure.number)


def test_display_options_falls_back_for_legend_layout_and_save_errors(
    tmp_path, monkeypatch, capsys
) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    display.figure_close = True
    legend_calls = []

    class Axis:
        def legend(self, **kwargs):
            legend_calls.append(kwargs)
            if len(legend_calls) == 1:
                raise RuntimeError("automatic legend failed")

    figure = Mock()
    figure.tight_layout.side_effect = RuntimeError("layout failed")
    figure.savefig.side_effect = OSError("read-only target")
    close = Mock()
    monkeypatch.setattr(plt, "close", close)

    display.save_and_close(
        figure,
        "summary.png",
        ax=Axis(),
        with_legend=True,
    )

    assert [call["loc"] for call in legend_calls] == ["best", "upper right"]
    figure.subplots_adjust.assert_called_once_with(top=0.9, bottom=0.1, hspace=0.4)
    assert "read-only target" in capsys.readouterr().out
    close.assert_called_once_with(figure)


def test_display_options_uses_fixed_margins_for_tight_layout_warning(tmp_path) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    display.figure_close = False
    figure = Mock()

    def warn_about_layout():
        import warnings

        warnings.warn("Tight layout not applied: axes are incompatible", stacklevel=2)

    figure.tight_layout.side_effect = warn_about_layout

    display.save_and_close(figure, "summary.png")

    figure.subplots_adjust.assert_called_once_with(top=0.9, bottom=0.1, hspace=0.4)
    figure.savefig.assert_called_once()


def test_figure_close_fx_respects_save_and_close_flags(tmp_path, monkeypatch) -> None:
    display = runtime.DisplayOptions()
    display.directory = tmp_path
    display.figure_save = True
    display.figure_close = True
    savefig = Mock()
    close = Mock()
    monkeypatch.setattr(plt, "savefig", savefig)
    monkeypatch.setattr(plt, "close", close)

    display.figure_close_fx("diagnostic.png")

    savefig.assert_called_once_with(tmp_path / "diagnostic.png", dpi=300)
    close.assert_called_once_with("all")


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
