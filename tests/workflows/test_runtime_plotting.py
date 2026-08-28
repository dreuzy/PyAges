# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for workflow runtime plotting backend selection."""

import matplotlib

from pyages.workflows.runtime.plotting import configure_backend


def test_configure_backend_respects_environment(monkeypatch) -> None:
    selected_backends = []
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setattr(matplotlib, "use", selected_backends.append)

    assert configure_backend(force_inline=True) is False
    assert selected_backends == ["Agg"]
