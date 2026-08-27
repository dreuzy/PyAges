# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Runtime configuration helpers (display and timing).
"""

from __future__ import annotations

import time
import warnings
from pathlib import Path

import numpy as np


class DisplayOptions:
    """Display and figure-output options."""

    __slots__ = ("text", "figure", "figure_close", "figure_save", "directory")

    def __init__(self) -> None:
        """Initialize non-interactive display defaults without an output path."""
        self.text = False
        self.figure = False
        self.figure_close = True
        self.figure_save = False
        self.directory: str | Path | None = None

    def save_and_close(
        self, fig, filename, method="", dpi=300, ax=None, with_legend=False
    ):
        """Save and optionally close a Matplotlib figure.

        The helper applies a tight layout, falls back to fixed margins when
        Matplotlib cannot satisfy it, and controls legend placement explicitly.
        """
        import matplotlib.pyplot as plt

        filepath = Path(self.directory) / method / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if ax is not None:
            if with_legend:
                try:
                    ax.legend(loc="best", fontsize=8)
                except Exception:
                    ax.legend(loc="upper right", fontsize=8)
            else:
                leg = ax.get_legend()
                if leg is not None:
                    leg.remove()

        try:
            with warnings.catch_warnings(record=True) as wlist:
                warnings.simplefilter("always")
                fig.tight_layout()
                for w in wlist:
                    if "Tight layout not applied" in str(w.message):
                        fig.subplots_adjust(top=0.9, bottom=0.1, hspace=0.4)
        except Exception:
            fig.subplots_adjust(top=0.9, bottom=0.1, hspace=0.4)

        try:
            fig.savefig(filepath, dpi=dpi)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde : {e}")

        if self.figure_close:
            plt.close(fig)

    def figure_close_fx(self, filename):
        """Save the active pyplot figure when requested, then close figures."""
        import matplotlib.pyplot as plt

        if self.figure_save and self.directory is not None:
            plt.savefig(Path(self.directory) / filename, dpi=300)
        if self.figure_close:
            plt.close("all")


def subdivide_interval(lower, upper, subdivision_count):
    """Return both endpoints and every regular subdivision boundary."""
    if subdivision_count <= 0:
        raise ValueError("subdivision_count must be positive")
    return (
        lower + (upper - lower) * np.arange(subdivision_count + 1) / subdivision_count
    )


class SimulationTimer:
    """Track elapsed time and estimate remaining simulation time."""

    __slots__ = (
        "simul_total",
        "time_start",
        "time_inter_start",
        "time_inter_end",
        "simul_current",
        "init_yes",
    )

    def __init__(self, nsim=1):
        """Initialize a timer for ``nsim`` top-level simulations."""
        self.simul_total = nsim
        self.time_start = 0
        self.time_inter_start = 0
        self.time_inter_end = 0
        self.simul_current = 0
        self.init_yes = False

    def initialize(self, nb):
        """Start timing once and multiply the total by ``nb`` inner runs."""
        if not self.init_yes:
            self.time_start = time.time()
            self.time_inter_start = time.time()
            self.simul_total = nb * self.simul_total
            self.init_yes = True

    def actualize(self, nb=1):
        """Advance the completed count and print elapsed and remaining hours."""
        self.time_inter_end = time.time()
        self.simul_current += nb
        elapsed = (self.time_inter_end - self.time_start) / 3600
        remaining = (
            (self.time_inter_end - self.time_start)
            * (self.simul_total / self.simul_current - 1)
            / 3600
        )
        line = f"time elapsed = {elapsed:.4f} h | time remaining = {remaining:.4f} h"
        end_char = "\n" if self.simul_current >= self.simul_total else "\r"
        print(line, end=end_char, flush=True)


__all__ = ["DisplayOptions", "SimulationTimer", "subdivide_interval"]
