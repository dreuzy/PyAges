# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file provides display, interval, and timing helpers used during workflows.

"""Translate runtime options into figure paths, grids, and progress estimates.

``DisplayOptions`` keeps text, figure, save, and close policies together and
constructs output paths consistently for each calibration method.
``subdivide_interval`` turns validated bounds into regularly spaced numerical
values without embedding that mechanics in workflow code.

``SimulationTimer`` measures completed iterations and reports elapsed time plus
an estimate for the remaining work. These helpers control execution presentation
and scheduling information; they do not alter scientific calculations.
"""

from __future__ import annotations

import operator
import time
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

    def figure_path(
        self,
        filename: str | Path,
        *,
        method: str | Path | None = None,
    ) -> Path | None:
        """Return the configured output path, or ``None`` when saving is off."""
        if not self.figure_save:
            return None
        if self.directory is None:
            raise ValueError("directory must be configured when figure_save is enabled")

        path = Path(self.directory)
        if method is not None:
            path /= method
        return path / filename


def subdivide_interval(lower, upper, subdivision_count):
    """Return both endpoints and every regular subdivision boundary."""
    if isinstance(subdivision_count, (bool, np.bool_)):
        raise ValueError("subdivision_count must be an integer >= 1")
    try:
        count = operator.index(subdivision_count)
    except TypeError as exc:
        raise ValueError("subdivision_count must be an integer >= 1") from exc
    if count < 1:
        raise ValueError("subdivision_count must be an integer >= 1")
    return np.linspace(lower, upper, count + 1)


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
