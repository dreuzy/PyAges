# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Created on Wed Mar 24 20:35:54 2021

Matplotlib runtime helpers for packaged workflows.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def configure_backend(force_inline=False):
    """
    Purpose
    -------
    Configure matplotlib backend depending on environment.

    Returns
    -------
    bool
        True when running inside an IPython kernel.
    """
    import matplotlib

    configured_backend = os.environ.get("MPLBACKEND")
    if configured_backend:
        matplotlib.use(configured_backend)
        return False

    try:
        from IPython import get_ipython

        ipy = get_ipython()
        if ipy is not None:
            ipy.run_line_magic("matplotlib", "inline")
        if ipy is not None or force_inline:
            try:
                import matplotlib.pyplot as plt

                plt.switch_backend("module://matplotlib_inline.backend_inline")
            except Exception:
                pass
            return True
        matplotlib.use("TkAgg")
        return False
    except Exception:
        matplotlib.use("TkAgg")
        return False


def enable_interactive(plt):
    """
    Purpose
    -------
    Enable interactive mode for long-running scripts.
    """
    plt.ion()


def show_figures(plt, is_interactive):
    """
    Purpose
    -------
    Flush figures in interactive mode.
    """
    if is_interactive:
        plt.show()


@dataclass(frozen=True)
class PlotSession:
    """Local plotting state for one workflow execution."""

    pyplot: Any
    interactive: bool

    @classmethod
    def start(cls, force_inline: bool = False) -> "PlotSession":
        """Configure Matplotlib and return the plotting state for one run."""
        interactive = configure_backend(force_inline=force_inline)
        import matplotlib.pyplot as plt

        enable_interactive(plt)
        return cls(pyplot=plt, interactive=interactive)

    def show(self) -> None:
        """Flush the current figure when the workflow is interactive."""
        show_figures(self.pyplot, self.interactive)

    def close(self, figure) -> None:
        """Close a completed figure."""
        self.pyplot.close(figure)

    def finish(self) -> None:
        """Block on figures only for a non-interactive desktop run."""
        if not self.interactive:
            self.pyplot.show(block=True)


__all__ = [
    "PlotSession",
    "configure_backend",
    "enable_interactive",
    "show_figures",
]
