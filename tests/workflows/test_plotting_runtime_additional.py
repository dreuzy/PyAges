# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Additional backend selection and plotting-session lifecycle tests."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import Mock

import matplotlib
import matplotlib.pyplot as plt

from pyages.workflows import plotting_runtime


def _install_fake_ipython(monkeypatch, get_ipython) -> None:
    """Expose the optional IPython hook without requiring the examples extra."""
    module = ModuleType("IPython")
    module.get_ipython = get_ipython
    monkeypatch.setitem(sys.modules, "IPython", module)


def test_configure_backend_selects_inline_for_ipython_or_forced_mode(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MPLBACKEND", raising=False)
    switch_backend = Mock()
    monkeypatch.setattr(plt, "switch_backend", switch_backend)
    _install_fake_ipython(monkeypatch, lambda: None)

    assert plotting_runtime.configure_backend(force_inline=True) is True
    switch_backend.assert_called_once_with("module://matplotlib_inline.backend_inline")


def test_configure_backend_selects_desktop_and_recovers_from_detection_error(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MPLBACKEND", raising=False)
    selected = []
    monkeypatch.setattr(matplotlib, "use", selected.append)
    _install_fake_ipython(monkeypatch, lambda: None)

    assert plotting_runtime.configure_backend(force_inline=False) is False
    assert selected == ["TkAgg"]

    selected.clear()

    def detection_failure():
        raise RuntimeError("IPython detection failed")

    _install_fake_ipython(monkeypatch, detection_failure)
    assert plotting_runtime.configure_backend(force_inline=False) is False
    assert selected == ["TkAgg"]


def test_plot_session_manages_interactive_figure_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(plotting_runtime, "configure_backend", lambda **_kwargs: True)
    ion = Mock()
    show = Mock()
    close = Mock()
    monkeypatch.setattr(plt, "ion", ion)
    monkeypatch.setattr(plt, "show", show)
    monkeypatch.setattr(plt, "close", close)

    session = plotting_runtime.PlotSession.start(force_inline=True)
    figure = object()
    session.show()
    session.close(figure)
    session.finish()

    ion.assert_called_once_with()
    show.assert_called_once_with()
    close.assert_called_once_with(figure)


def test_plot_session_blocks_only_for_desktop_runs() -> None:
    pyplot = Mock()

    plotting_runtime.PlotSession(pyplot=pyplot, interactive=False).finish()

    pyplot.show.assert_called_once_with(block=True)
