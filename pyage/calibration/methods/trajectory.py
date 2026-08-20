"""Metropolis-Hastings configuration, proposal steps, and trajectories."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MHConfig:
    """Configuration of one Metropolis-Hastings calibration."""

    nstep: int = 10000
    burn_in: float = 0.2
    nskip: int = 10
    prior_option: bool = True
    prior_type: str = "parametric"
    likelihood: bool = True
    monitor: bool = True
    display_traj: bool = False
    display_text: bool = False
    prior_file: str = ""
    lpm_number: int = 10
    seed: int = 12345
    initial_params: dict[str, float] | None = None
    proposal_kind: str = "legacy_diagonal"
    proposal_scales: tuple[float, ...] | None = None
    proposal_covariance: tuple[tuple[float, ...], ...] | None = None
    proposal_multiplier: float = 1.0


@dataclass(frozen=True)
class TrajOptions:
    """Configuration for trajectory monitoring and display."""

    monitor: bool
    display: bool
    text: bool


class MHTrajectory:
    """Optional trajectory storage used to monitor an MCMC run."""

    def __init__(self, params: Iterable[str], nstep: int) -> None:
        names = [*params, "-log_posterior"]
        self.n_inc = len(names)
        self.path = pd.DataFrame(
            index=range(nstep),
            columns=[*names, "incrementation"],
        )

    def update(self, index: int, params: list[float], log_posterior: float) -> None:
        """Store the state reached at one MCMC iteration."""
        values = copy.deepcopy(params)
        values.extend([-log_posterior, 0])
        self.path.iloc[index, :] = values

    def inc_one(self, index: int) -> None:
        """Mark an accepted proposal at one MCMC iteration."""
        self.path.iloc[index, self.n_inc] = 1

    def check(self) -> None:
        """Print the mean and standard deviation of stored columns."""
        for name in self.path:
            values = self.path[name].to_numpy()
            mean = np.nanmean(values, dtype="float")
            variance = np.nanvar(values, dtype="float")
            print(f"{mean:.4f}", f"{np.sqrt(variance):.4f}", "<> & σ of", name)

    def resize(self, size: int) -> None:
        """Discard unused preallocated trajectory rows."""
        self.path.drop(self.path.tail(self.path.shape[0] - size).index, inplace=True)

    def plot(self, directory_name: str | Path | None) -> None:
        """Plot each trajectory column and optionally save it."""
        for name in self.path:
            axis = self.path.plot.line(y=name, logy=False)
            figure = axis.get_figure()
            if directory_name is not None:
                figure.savefig(Path(directory_name) / f"MH_trajectory_{name}")
                plt.close(figure)


class MHStep:
    """Proposal-step configuration for Metropolis-Hastings."""

    def __init__(self) -> None:
        self.method = "prop"
        self.value: int | dict[str, float] = 1
        self.prop = 0.1
        self.interval: int | dict[str, float] = 0

    def define_by_value(self) -> None:
        """Load explicit proposal steps from the model configuration."""
        self.method = "value"

    def define_by_prop(self, prop: float) -> None:
        """Set proposal steps as a proportion of parameter ranges."""
        self.method = "prop"
        self.prop = prop

    def define_value_by_interval(self, lpm: Any) -> None:
        """Compute proposal steps from model parameter ranges."""
        intervals = {name: lpm.get_param_range(name) for name in lpm.p}
        self.interval = intervals
        self.value = {
            name: self.prop * interval for name, interval in intervals.items()
        }

    def load_MHsteps(self, lpm: Any) -> None:
        """Load explicit proposal steps from ``params.yaml``."""
        from pyage.data_io import lpm_params

        params = lpm_params.load_params(lpm.name, lpm.lpm_data_directory)
        values = lpm_params.get_steps(params)
        if not values:
            raise ValueError(f"No MH step values found in params.yaml for {lpm.name}.")
        self.value = values

    def prepare(self, lpm: Any) -> None:
        """Resolve proposal values for a concrete model."""
        if self.method == "prop":
            self.define_value_by_interval(lpm)
        else:
            self.load_MHsteps(lpm)

    def save_param(self, data: dict[str, Any]) -> None:
        """Append proposal-step settings to a result mapping."""
        data["MH_delta_method"] = self.method
        if not isinstance(self.value, dict):
            return
        for name, value in self.value.items():
            data[f"MH_delta_{name}"] = value


# Compatibility aliases retained for existing callers.
MH_Trajectory = MHTrajectory
MH_step = MHStep

__all__ = [
    "MHConfig",
    "MHStep",
    "MHTrajectory",
    "MH_Trajectory",
    "MH_step",
    "TrajOptions",
]
