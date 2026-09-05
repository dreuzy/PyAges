# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file checks and stores every setting used to run one MH chain.

"""Define the complete configuration for one Metropolis--Hastings chain.

The configuration covers the number of transitions, burn-in and thinning,
random seed, prior and likelihood choices, starting parameters, proposal type,
and optional monitoring. Values are validated and copied when the object is
created so that an invalid or later-mutated setting cannot reach the sampler.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from pyages.calibration.methods.mh._immutable import FrozenMapping
from pyages.calibration.sampling_schedule import strict_retained_sample_count


def _frozen_initial_params(
    initial_params: Mapping[str, float] | None,
) -> Mapping[str, float] | None:
    """Return a detached read-only parameter mapping."""
    if initial_params is None:
        return None
    if not isinstance(initial_params, Mapping):
        raise TypeError("initial_params must be a parameter mapping or None")
    copied: dict[str, float] = {}
    for name, raw_value in initial_params.items():
        if not isinstance(name, str) or not name:
            raise ValueError("initial_params names must be non-empty strings")
        if isinstance(raw_value, bool):
            raise ValueError("initial_params values must be finite numbers")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("initial_params values must be finite numbers") from exc
        if not math.isfinite(value):
            raise ValueError("initial_params values must be finite numbers")
        copied[name] = value
    return FrozenMapping(copied)


def _numeric_tuple(values: Iterable[float], name: str) -> tuple[float, ...]:
    """Detach one finite numeric vector from caller-owned storage."""
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a sequence or None")
    try:
        raw_values = tuple(values)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a sequence or None") from exc
    if any(isinstance(value, bool) for value in raw_values):
        raise TypeError(f"{name} must not contain boolean values")
    try:
        copied = tuple(float(value) for value in raw_values)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a sequence or None") from exc
    if not all(math.isfinite(value) for value in copied):
        raise ValueError(f"{name} must contain only finite numbers")
    return copied


def _numeric_matrix(
    values: Iterable[Iterable[float]],
) -> tuple[tuple[float, ...], ...]:
    """Detach one finite numeric matrix from caller-owned storage."""
    if isinstance(values, (str, bytes)):
        raise TypeError("proposal_covariance must be a matrix or None")
    try:
        copied = tuple(_numeric_tuple(row, "proposal_covariance") for row in values)
    except TypeError as exc:
        raise TypeError("proposal_covariance must be a matrix or None") from exc
    return copied


def _validate_exact_booleans(instance: object, names: tuple[str, ...]) -> None:
    """Require exact booleans for flags instead of accepting integers."""
    for name in names:
        if type(getattr(instance, name)) is not bool:
            raise TypeError(f"{name} must be a boolean")


def _validated_covariance(
    covariance_values: tuple[tuple[float, ...], ...],
) -> None:
    """Validate the shape and linear-algebra contract of a covariance."""
    covariance = np.asarray(covariance_values, dtype=float)
    if (
        covariance.ndim != 2
        or covariance.shape[0] == 0
        or covariance.shape[0] != covariance.shape[1]
    ):
        raise ValueError("proposal_covariance must be a non-empty square matrix")
    if not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-12):
        raise ValueError("proposal_covariance must be symmetric")
    if np.any(np.linalg.eigvalsh(covariance) <= 0.0):
        raise ValueError("proposal_covariance must be positive definite")


@dataclass(frozen=True)
class MHConfig:
    """Reproducibility controls for one Metropolis--Hastings chain.

    ``nstep`` counts transitions, including rejected proposals. Samples are
    retained when the zero-based iteration ``i`` satisfies both
    ``i > burn_in * nstep`` and ``i % nskip == 0``; rejected transitions retain
    the previous state. ``burn_in`` is a fraction, ``nskip`` is the thinning
    interval, and ``seed`` initializes NumPy's ``default_rng``.

    With ``likelihood=True``, the target contains
    ``exp(-chi_square / 2)`` under independent Gaussian errors. With
    ``prior_option=True``, the configured prior density is multiplied into the
    target. Values outside calibration ranges have zero target density.

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
    initial_params: Mapping[str, float] | None = None
    proposal_kind: str = "componentwise"
    componentwise_source: str = "bounds"
    componentwise_fraction: float = 0.1
    proposal_scales: tuple[float, ...] | None = None
    proposal_covariance: tuple[tuple[float, ...], ...] | None = None
    proposal_multiplier: float = 1.0

    def __post_init__(self) -> None:
        """Reject invalid controls before allocating scientific objects."""
        self._freeze_payloads()
        self._validate_chain_controls()
        self._validate_proposal_controls()

    def _freeze_payloads(self) -> None:
        """Detach and freeze caller-owned mappings and proposal sequences."""
        object.__setattr__(
            self,
            "initial_params",
            _frozen_initial_params(self.initial_params),
        )
        if self.proposal_scales is not None:
            object.__setattr__(
                self,
                "proposal_scales",
                _numeric_tuple(self.proposal_scales, "proposal_scales"),
            )
        if self.proposal_covariance is not None:
            object.__setattr__(
                self,
                "proposal_covariance",
                _numeric_matrix(self.proposal_covariance),
            )

    def _validate_chain_controls(self) -> None:
        _validate_exact_booleans(
            self,
            (
                "prior_option",
                "likelihood",
                "monitor",
                "display_traj",
                "display_text",
            ),
        )
        self._validate_schedule()
        self._validate_prior_controls()

    def _validate_schedule(self) -> None:
        """Validate chain length, burn-in, thinning, and seed."""
        if (
            isinstance(self.nstep, bool)
            or not isinstance(self.nstep, int)
            or self.nstep <= 0
        ):
            raise ValueError("nstep must be a positive integer")
        if (
            isinstance(self.burn_in, bool)
            or not isinstance(self.burn_in, (int, float))
            or not math.isfinite(self.burn_in)
            or not 0.0 <= self.burn_in < 1.0
        ):
            raise ValueError("burn_in must be finite and in [0, 1)")
        if (
            isinstance(self.nskip, bool)
            or not isinstance(self.nskip, int)
            or self.nskip <= 0
        ):
            raise ValueError("nskip must be a positive integer")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or self.seed < 0
        ):
            raise ValueError("seed must be a non-negative integer")
        if self.retained_sample_count() == 0:
            raise ValueError(
                "nstep, burn_in, and nskip retain no samples under the strict "
                "burn-in rule"
            )

    def _validate_prior_controls(self) -> None:
        """Validate the selected prior source and its required file."""
        if self.prior_type not in {"parametric", "empirical"}:
            raise ValueError("prior_type must be 'parametric' or 'empirical'")
        if not isinstance(self.prior_file, str):
            raise TypeError("prior_file must be a string")
        if self.prior_option and self.prior_type == "empirical" and not self.prior_file:
            raise ValueError(
                "prior_file must be non-empty when an empirical prior is enabled"
            )

    def _validate_proposal_controls(self) -> None:
        self._validate_proposal_selection()
        self._validate_proposal_payload()

    def _validate_proposal_selection(self) -> None:
        """Validate proposal names and scalar controls."""
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
            isinstance(self.componentwise_fraction, bool)
            or not isinstance(self.componentwise_fraction, (int, float))
            or not math.isfinite(self.componentwise_fraction)
            or self.componentwise_fraction <= 0.0
        ):
            raise ValueError("componentwise_fraction must be finite and positive")
        if (
            isinstance(self.proposal_multiplier, bool)
            or not math.isfinite(self.proposal_multiplier)
            or self.proposal_multiplier <= 0.0
        ):
            raise ValueError("proposal_multiplier must be finite and positive")

    def _validate_proposal_payload(self) -> None:
        """Validate settings accepted by the selected proposal kind."""
        if self.proposal_scales is not None and (
            not self.proposal_scales
            or any(scale <= 0.0 for scale in self.proposal_scales)
        ):
            raise ValueError("proposal_scales must contain positive values")
        if self.proposal_covariance is not None:
            _validated_covariance(self.proposal_covariance)
        self._validate_payload_for_kind()

    def _validate_payload_for_kind(self) -> None:
        """Reject proposal payloads that do not belong to the selected kind."""
        if self.proposal_kind == "componentwise":
            has_explicit_payload = (
                self.proposal_scales is not None
                or self.proposal_covariance is not None
                or self.proposal_multiplier != 1.0
            )
            if has_explicit_payload:
                raise ValueError(
                    "componentwise proposals do not accept explicit scales, "
                    "covariance, or multiplier"
                )
            return
        if self.proposal_kind in {"diagonal", "sum_difference"}:
            if self.proposal_scales is None:
                raise ValueError(f"{self.proposal_kind} requires proposal_scales")
            if self.proposal_covariance is not None:
                raise ValueError(
                    f"{self.proposal_kind} does not accept proposal_covariance"
                )
            return
        if self.proposal_covariance is None:
            raise ValueError(f"{self.proposal_kind} requires proposal_covariance")
        if self.proposal_scales is not None:
            raise ValueError(f"{self.proposal_kind} does not accept proposal_scales")

    def should_retain(self, iteration: int) -> bool:
        """Return whether one zero-based transition is retained."""
        return (
            0 <= iteration < self.nstep
            and iteration > self.burn_in * self.nstep
            and iteration % self.nskip == 0
        )

    def retained_sample_count(self) -> int:
        """Return the retained row count in constant time."""
        return strict_retained_sample_count(self.nstep, self.burn_in, self.nskip)


__all__ = ["MHConfig"]
