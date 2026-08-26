"""Tests for workflow plotting backend selection."""

import matplotlib

from pyage.workflows.plotting_runtime import configure_backend


def test_configure_backend_respects_environment(monkeypatch) -> None:
    selected_backends = []
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setattr(matplotlib, "use", selected_backends.append)

    assert configure_backend(force_inline=True) is False
    assert selected_backends == ["Agg"]
