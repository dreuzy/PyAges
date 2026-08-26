"""Metropolis-Hastings configuration, proposal steps, and trajectories."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MHConfig:
    """Reproducibility controls for one Metropolis-Hastings chain.

    ``nstep`` counts transitions, including rejected proposals. Samples are
    retained when the zero-based iteration ``i`` satisfies both
    ``i > burn_in * nstep`` and ``i % nskip == 0``; rejected transitions retain
    the previous state. ``burn_in`` is a fraction, ``nskip`` is the thinning
    interval, and ``seed`` initializes NumPy's ``default_rng``.

    With ``likelihood=True``, the target contains
    ``exp(-chi_square / 2)`` under independent Gaussian errors. With
    ``prior_option=True``, the configured prior density is multiplied into the
    target. Parameter bounds have zero target density.

    ``proposal_kind`` selects the coordinate system and covariance convention:
    ``componentwise`` draws one scalar normal increment per native parameter,
    using either configured steps or fractions of parameter ranges;
    ``diagonal`` and ``correlated`` use fixed native-coordinate Gaussian
    proposals; ``sum_difference`` is a two-parameter linear transform; and
    ``scipy_ig_correlated`` proposes in SciPy IG shape/scale/shift coordinates
    with the state-dependent Hastings correction. ``proposal_scales`` are
    standard deviations in the selected coordinates, while
    ``proposal_covariance`` contains squared coordinate units.

    Notes
    -----
    Burn-in and thinning do not establish convergence or effective sample
    size. Publication analyses must report independent-chain diagnostics in
    addition to these settings; see ``docs/scientific-methods.md`` and
    ``docs/reports/mh_proposal_qualification.md``.
    """

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
    seed: int = 12345
    initial_params: dict[str, float] | None = None
    proposal_kind: str = "componentwise"
    componentwise_source: str = "bounds"
    componentwise_fraction: float = 0.1
    proposal_scales: tuple[float, ...] | None = None
    proposal_covariance: tuple[tuple[float, ...], ...] | None = None
    proposal_multiplier: float = 1.0

    def __post_init__(self) -> None:
        """Reject invalid controls before allocating or running a chain."""
        if (
            isinstance(self.nstep, bool)
            or not isinstance(self.nstep, int)
            or self.nstep <= 0
        ):
            raise ValueError("nstep must be a positive integer")
        if not math.isfinite(self.burn_in) or not 0.0 <= self.burn_in < 1.0:
            raise ValueError("burn_in must be finite and in [0, 1)")
        if (
            isinstance(self.nskip, bool)
            or not isinstance(self.nskip, int)
            or self.nskip <= 0
        ):
            raise ValueError("nskip must be a positive integer")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if self.prior_type not in {"parametric", "empirical"}:
            raise ValueError("prior_type must be 'parametric' or 'empirical'")
        valid_kinds = {
            "componentwise",
            "diagonal",
            "correlated",
            "sum_difference",
            "scipy_ig_correlated",
        }
        if self.proposal_kind not in valid_kinds:
            raise ValueError(f"Unknown proposal_kind: {self.proposal_kind!r}")
        if self.componentwise_source not in {"bounds", "model"}:
            raise ValueError("componentwise_source must be 'bounds' or 'model'")
        if (
            not math.isfinite(self.componentwise_fraction)
            or self.componentwise_fraction <= 0.0
        ):
            raise ValueError("componentwise_fraction must be finite and positive")


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

    def update(
        self,
        index: int,
        params: list[float],
        log_posterior: float,
        *,
        accepted: bool,
    ) -> None:
        """Store the state reached at one MCMC iteration."""
        values = copy.deepcopy(params)
        values.extend([-log_posterior, int(accepted)])
        self.path.iloc[index, :] = values

    def check(self) -> None:
        """Print the mean and standard deviation of stored columns."""
        for name in self.path:
            values = self.path[name].to_numpy()
            mean = np.nanmean(values, dtype="float")
            variance = np.nanvar(values, dtype="float")
            print(f"{mean:.4f}", f"{np.sqrt(variance):.4f}", "mean & sigma of", name)

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

    def __init__(self, source: str, fraction: float) -> None:
        self.source = source
        self.fraction = fraction
        self.value: dict[str, float] = {}

    def _derive_from_bounds(self, lpm: Any) -> None:
        """Compute proposal steps from model parameter ranges."""
        intervals = {name: lpm.get_param_range(name) for name in lpm.p}
        self.value = {
            name: self.fraction * interval for name, interval in intervals.items()
        }

    def _load_configured_values(self, lpm: Any) -> None:
        """Load explicit proposal steps from ``params.yaml``."""
        from pyage.data_io import lpm_params

        params = lpm_params.load_params(lpm.name, lpm.lpm_data_directory)
        values = lpm_params.get_steps(params)
        if not values:
            raise ValueError(f"No MH step values found in params.yaml for {lpm.name}.")
        expected = list(lpm.p)
        missing = [name for name in expected if name not in values]
        extra = [name for name in values if name not in lpm.p]
        if missing or extra:
            raise ValueError(
                "Configured MH steps must match the LPM parameters "
                f"(missing={missing}, extra={extra})"
            )
        self.value = {name: float(values[name]) for name in expected}
        if any(
            not math.isfinite(value) or value <= 0.0 for value in self.value.values()
        ):
            raise ValueError("Configured MH steps must be finite and positive")

    def prepare(self, lpm: Any) -> None:
        """Resolve proposal values for a concrete model."""
        if self.source == "bounds":
            self._derive_from_bounds(lpm)
        else:
            self._load_configured_values(lpm)

    def add_metadata(self, data: dict[str, Any]) -> None:
        """Append proposal-step settings to a result mapping."""
        data["MH_delta_source"] = self.source
        if self.source == "bounds":
            data["MH_delta_fraction"] = self.fraction
        for name, value in self.value.items():
            data[f"MH_delta_{name}"] = value


__all__ = [
    "MHConfig",
    "MHStep",
    "MHTrajectory",
    "TrajOptions",
]
