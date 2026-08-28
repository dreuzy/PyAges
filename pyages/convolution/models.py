# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Validated value objects shared by the convolution pipeline.

These records make cached numerical inputs immutable and expose compact
diagnostics without coupling callers to the integration implementation.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class PreparedTracerGrid:
    """Immutable tracer-response samples cached for one observation date.

    Attributes
    ----------
    date : float
        Finite observation date represented by the grid.
    edges : numpy.ndarray
        Strictly increasing age-bin edges. A one-element array represents an
        empty integration window.
    k_left, k_mid, k_right : numpy.ndarray
        Tracer responses at the left edge, midpoint, and right edge of every
        bin. Arrays are copied and marked read-only at construction.
    """

    date: float
    edges: npt.NDArray[np.float64]
    k_left: npt.NDArray[np.float64]
    k_mid: npt.NDArray[np.float64]
    k_right: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        """Validate the grid topology and protect cached arrays from mutation."""
        date = float(self.date)
        if not np.isfinite(date):
            raise ValueError("PreparedTracerGrid.date must be finite")

        arrays: dict[str, npt.NDArray[np.float64]] = {}
        for name in ("edges", "k_left", "k_mid", "k_right"):
            values = np.array(getattr(self, name), dtype=float, copy=True)
            if values.ndim != 1 or not np.all(np.isfinite(values)):
                raise ValueError(f"PreparedTracerGrid.{name} must be a finite vector")
            arrays[name] = values

        edges = arrays["edges"]
        if edges.size < 1:
            raise ValueError("PreparedTracerGrid.edges must contain at least one value")
        if edges.size > 1 and np.any(np.diff(edges) <= 0.0):
            raise ValueError("PreparedTracerGrid.edges must be strictly increasing")

        bin_count = edges.size - 1
        for name in ("k_left", "k_mid", "k_right"):
            if arrays[name].size != bin_count:
                raise ValueError(
                    f"PreparedTracerGrid.{name} must contain {bin_count} values"
                )

        object.__setattr__(self, "date", date)
        # Copies sever aliases to caller-owned arrays; read-only flags then make
        # a cached grid a stable snapshot throughout repeated LPM evaluations.
        for name, values in arrays.items():
            values.setflags(write=False)
            object.__setattr__(self, name, values)

    @property
    def midpoints(self) -> npt.NDArray[np.float64]:
        """Return bin midpoints without storing redundant state."""
        return 0.5 * (self.edges[:-1] + self.edges[1:])


@dataclass(frozen=True)
class ConvolutionDiagnostics:
    """Diagnostics from the latest continuous or mixed convolution.

    Attributes
    ----------
    window_mass : float
        Probability mass represented in the available tracer-history window.
        Omitted older mass is not renormalized.
    n_bins : int
        Number of prepared tracer-response bins used for integration.
    min_weight : float
        Smallest raw CDF difference before round-off-sized negative values are
        clipped.
    clipped_weight_count : int
        Number of negative bin weights clipped as floating-point round-off.

    Notes
    -----
    Pure Dirac and double-Dirac convolutions do not create diagnostics; use
    :meth:`pyages.convolution.convolution.Convolution.window_mass` for their
    represented mass.
    """

    window_mass: float
    n_bins: int
    min_weight: float
    clipped_weight_count: int


class ConvolutionError(Exception):
    """Report a violated numerical contract during preparation or execution."""
