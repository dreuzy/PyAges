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
import pytest

from pyages.workflows.runtime import plotting


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

    assert plotting.configure_backend(force_inline=True) is True
    switch_backend.assert_called_once_with("module://matplotlib_inline.backend_inline")


def test_configure_backend_preserves_auto_backend_and_recovers_from_detection_error(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MPLBACKEND", raising=False)
    select_backend = Mock()
    monkeypatch.setattr(matplotlib, "use", select_backend)
    _install_fake_ipython(monkeypatch, lambda: None)

    assert plotting.configure_backend(force_inline=False) is False
    select_backend.assert_not_called()

    def detection_failure():
        raise RuntimeError("IPython detection failed")

    _install_fake_ipython(monkeypatch, detection_failure)
    assert plotting.configure_backend(force_inline=False) is False
    select_backend.assert_not_called()


def test_configure_backend_reports_a_forced_inline_failure(monkeypatch) -> None:
    monkeypatch.delenv("MPLBACKEND", raising=False)
    _install_fake_ipython(monkeypatch, lambda: None)
    monkeypatch.setattr(
        plt,
        "switch_backend",
        Mock(side_effect=ImportError("matplotlib-inline missing")),
    )

    with pytest.raises(RuntimeError, match="inline Matplotlib backend"):
        plotting.configure_backend(force_inline=True)


def test_plot_session_manages_interactive_figure_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(plotting, "configure_backend", lambda **_kwargs: True)
    ion = Mock()
    show = Mock()
    close = Mock()
    monkeypatch.setattr(plt, "ion", ion)
    monkeypatch.setattr(plt, "show", show)
    monkeypatch.setattr(plt, "close", close)

    session = plotting.PlotSession.start(force_inline=True)
    figure = object()
    session.show()
    session.close(figure)
    session.close_all()
    session.finish()

    ion.assert_called_once_with()
    show.assert_called_once_with()
    assert close.call_args_list[0].args == (figure,)
    assert close.call_args_list[1].args == ("all",)


def test_plot_session_blocks_only_for_desktop_runs() -> None:
    pyplot = Mock()

    plotting.PlotSession(pyplot=pyplot, interactive=False).finish()

    pyplot.show.assert_called_once_with(block=True)
