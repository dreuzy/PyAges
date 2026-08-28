# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Retained Metropolis--Hastings trajectory diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class MHTrajectory:
    """Optional diagnostic storage for retained MCMC states.

    Rows follow the post-burn-in/thinning schedule. Rejected retained
    transitions repeat the current state and store ``incrementation=0``.
    """

    def __init__(self, params: Iterable[str], nstep: int) -> None:
        """Preallocate numeric trajectory columns and diagnostics."""
        if nstep < 0:
            raise ValueError("nstep must be non-negative")
        columns = [*params, "-log_posterior", "incrementation"]
        self.path = pd.DataFrame(
            np.full((nstep, len(columns)), np.nan, dtype=float),
            columns=columns,
        )

    def update(
        self,
        index: int,
        params: Sequence[float],
        log_posterior: float,
        *,
        accepted: bool,
    ) -> None:
        """Store one retained state and whether its proposal was accepted."""
        if not 0 <= index < len(self.path):
            raise IndexError("trajectory index is outside preallocated storage")
        values = [*params, -log_posterior, float(accepted)]
        if len(values) != len(self.path.columns):
            raise ValueError("trajectory parameter count does not match its columns")
        self.path.iloc[index, :] = values

    def summary(self) -> pd.DataFrame:
        """Return means and population standard deviations for stored columns."""
        values = self.path.to_numpy(dtype=float)
        return pd.DataFrame(
            {
                "mean": np.nanmean(values, axis=0),
                "std": np.sqrt(np.nanvar(values, axis=0)),
            },
            index=self.path.columns,
        )

    def check(self) -> pd.DataFrame:
        """Return the retained-state summary kept by the historical API name."""
        return self.summary()

    def resize(self, size: int) -> None:
        """Discard unused preallocated rows after validating the final size."""
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("trajectory size must be an integer")
        if not 0 <= size <= len(self.path):
            raise ValueError("trajectory size must fit preallocated storage")
        self.path = self.path.iloc[:size].copy()

    def plot(self, directory_name: str | Path | None) -> None:
        """Plot each trajectory column and optionally save it."""
        for name in self.path:
            axis = self.path.plot.line(y=name, logy=False)
            figure = axis.get_figure()
            if directory_name is not None:
                figure.savefig(Path(directory_name) / f"MH_trajectory_{name}")
                plt.close(figure)


__all__ = ["MHTrajectory"]
