# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file manages Matplotlib setup and display behavior for workflows.

"""Configure plotting once and give workflows a consistent figure lifecycle.

Backend selection respects an explicit environment choice and otherwise adapts
to notebook, interactive desktop, or headless execution. The resulting runtime
state records whether figures can be displayed immediately or must only be
written to files.

``PlotSession`` delays importing ``pyplot`` until configuration is complete and
provides uniform show, close, close-all, and final blocking-display operations.
Scientific plotting modules remain responsible for figure contents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def configure_backend(force_inline: bool = False) -> bool:
    """Configure the Matplotlib backend for the current environment.

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
    except ImportError:
        ipy = None
    else:
        try:
            ipy = get_ipython()
        except Exception:
            # IPython is optional and third-party detection hooks may fail.
            ipy = None

    if ipy is None and not force_inline:
        return False

    try:
        if ipy is not None:
            ipy.run_line_magic("matplotlib", "inline")
        import matplotlib.pyplot as plt

        plt.switch_backend("module://matplotlib_inline.backend_inline")
    except Exception as exc:
        if force_inline:
            raise RuntimeError("The inline Matplotlib backend is unavailable") from exc
        return False
    return True


def enable_interactive(plt):
    """Enable interactive mode for long-running scripts."""
    plt.ion()


def show_figures(plt, is_interactive):
    """Flush figures in interactive mode."""
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

    def close_all(self) -> None:
        """Close every figure when a workflow aborts before normal completion."""
        self.pyplot.close("all")

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
