# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structural contracts used at LPM integration boundaries.

The protocols describe capabilities rather than requiring inheritance from
``LpmBase``. Internal models still inherit from that base class, while external
adapters and static type checkers can rely on these narrower, explicit roles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt
import pandas as pd


@runtime_checkable
class LpmParameterProtocol(Protocol):
    """Parameter and bounds operations required by calibration methods."""

    name: str
    p: dict[str, float]

    @property
    def lpm_data_directory(self) -> Path:
        """Return the root containing this model's parameter metadata."""

    @property
    def parameter_units(self) -> dict[str, str]:
        """Return physical units keyed by parameter name."""

    def get_param_names(self) -> list[str]:
        """Return parameter names in canonical calibration order."""

    def get_parameters_to_array(self) -> list[float]:
        """Return parameter values in canonical calibration order."""

    def set_param_from_array(self, param: npt.ArrayLike) -> None:
        """Replace parameters from their canonical ordered representation."""

    def get_param_range(self, param_name: str) -> float:
        """Return the configured range of one parameter."""

    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """Return ordered lower and upper parameter bounds."""

    def get_p_min(self, key: str) -> float:
        """Return one parameter's lower bound."""

    def get_p_max(self, key: str) -> float:
        """Return one parameter's upper bound."""

    def param_within_bounds_array(self, params: npt.ArrayLike) -> bool:
        """Validate an ordered parameter vector against model bounds."""


@runtime_checkable
class LpmModelProtocol(LpmParameterProtocol, Protocol):
    """Distribution and sampling operations used by LPM result analysis."""

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the transit-time probability density."""

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the transit-time cumulative distribution."""

    def cdf_inv(self, p: float) -> float:
        """Evaluate an inverse cumulative probability."""

    def moments_name(self) -> list[str]:
        """Return labels corresponding positionally to ``moments``."""

    def moments(self) -> list[float]:
        """Return the model's standard descriptive moments."""

    def sample_curve(
        self, kind: str, count: int
    ) -> tuple[np.ndarray, npt.ArrayLike]:
        """Evaluate a PDF or CDF on its plotting window."""

    def load_sample(
        self,
        frame: pd.DataFrame,
        selection: str = "line",
        rng: np.random.Generator | None = None,
        row: int = 0,
    ) -> int | None:
        """Load one parameter row and return its selected position."""


__all__ = ["LpmModelProtocol", "LpmParameterProtocol"]
