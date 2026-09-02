# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file records retained states from one MH chain for inspection and plots.

"""Record a lightweight trace of the retained states from one MH chain.

The trace contains parameter values, the negative log-posterior, and a flag
showing whether the retained transition was accepted. It can be summarized in
a table or plotted to help inspect the behavior of an individual chain. It is
optional monitoring data, not a second set of posterior samples.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class MHTrajectory:
    """Keep an optional inspection table for one chain's retained states.

    A row is added only when the normal burn-in and thinning schedule retains a
    transition. If a proposal was rejected, the row repeats the current
    parameter values and stores ``incrementation=0``. These repeated states are
    part of the Markov chain and are not removed.
    """

    def __init__(self, params: Iterable[str], nstep: int) -> None:
        """Preallocate numeric trajectory columns and diagnostics."""
        if isinstance(nstep, bool) or not isinstance(nstep, int) or nstep < 0:
            raise ValueError("nstep must be a non-negative integer")
        parameter_names = tuple(params)
        if (
            not parameter_names
            or any(not isinstance(name, str) or not name for name in parameter_names)
            or len(set(parameter_names)) != len(parameter_names)
        ):
            raise ValueError("trajectory parameters must be unique non-empty strings")
        columns = [*parameter_names, "-log_posterior", "incrementation"]
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
        if type(accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        if not 0 <= index < len(self.path):
            raise IndexError("trajectory index is outside preallocated storage")
        try:
            numeric_params = np.asarray(tuple(params), dtype=float)
            numeric_log_posterior = float(log_posterior)
        except (TypeError, ValueError) as exc:
            raise ValueError("trajectory values must be finite numbers") from exc
        if not np.all(np.isfinite(numeric_params)) or not np.isfinite(
            numeric_log_posterior
        ):
            raise ValueError("trajectory values must be finite numbers")
        values = [*numeric_params, -numeric_log_posterior, float(accepted)]
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
        directory = None if directory_name is None else Path(directory_name)
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
        for name in self.path:
            axis = self.path.plot.line(y=name, logy=False)
            figure = axis.get_figure()
            if directory is not None:
                figure.savefig(directory / f"MH_trajectory_{name}.png")
            plt.close(figure)


__all__ = ["MHTrajectory"]
