# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structural interfaces for tracer consumers.

``ConvolutionTracerProtocol`` is the narrow numerical contract required by
the convolution engine. ``TracerProtocol`` extends it with the summary
metadata historically exposed by :mod:`pyages.tracer.tracer_protocol`.
"""

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


@runtime_checkable
class TracerProtocol(ConvolutionTracerProtocol, Protocol):
    """Full historical tracer interface, including reporting summaries.

    Consumers that only perform convolution should depend on
    :class:`ConvolutionTracerProtocol`. This extended contract remains useful
    for reporting code and preserves the existing contributor interface.
    """

    @property
    def unit(self) -> str:
        """Concentration units (for example ``"pptv"`` or ``"TU"``)."""
        ...

    def mean_value(self, date: float) -> float:
        """Return a representative mean concentration at a reference date."""
        ...

    def max_value(self) -> float:
        """Return the maximum tracer-response value."""
        ...


__all__ = ["ConvolutionTracerProtocol", "TracerProtocol"]
