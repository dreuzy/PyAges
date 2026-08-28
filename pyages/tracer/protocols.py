# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structural interface required by tracer consumers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt


@runtime_checkable
class ConvolutionTracerProtocol(Protocol):
    """Structural interface required to evaluate a tracer convolution."""

    @property
    def name(self) -> str:
        """Tracer identifier (for example ``"cfc11"`` or ``"3H"``)."""
        ...

    @property
    def datemin(self) -> float:
        """Minimum recharge date represented by the tracer response."""
        ...

    @property
    def datemax(self) -> float:
        """Maximum recharge date represented by the tracer response."""
        ...

    def get_concentration(
        self,
        date: float | npt.NDArray[np.float64],
        time: float | npt.NDArray[np.float64],
    ) -> float | npt.NDArray[np.float64]:
        """Return the response for recharge ``date`` and elapsed ``time``."""
        ...

    @property
    def convolution_dates(self) -> npt.NDArray[np.float64] | None:
        """Return chronicle dates used as initial convolution-grid knots."""
        ...

    @property
    def convolution_initial_bins(self) -> int:
        """Return the initial bin count when chronicle dates are unavailable."""
        ...


__all__ = ["ConvolutionTracerProtocol"]
