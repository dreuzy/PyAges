# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file turns parameter names, bounds, and a target resolution into every
# point of a regular Cartesian grid. It also reshapes one result per point back
# into the same multidimensional layout for plotting and analysis.

"""Regular Cartesian grids used by systematic calibration exploration."""

from __future__ import annotations

from itertools import product
from math import ceil
from typing import Sequence

import numpy as np
import numpy.typing as npt

from pyages.config.runtime import subdivide_interval


class ParameterGrid:
    """Build and reshape a regular Cartesian parameter grid.

    ``target_size`` controls the resolution, not the exact number of points.
    Each axis contains one more point than the rounded-up root of the requested
    size because ``target_size`` determines subdivisions and both bounds are
    included. The last axis varies fastest in the Cartesian product.
    """

    def __init__(
        self,
        minima: Sequence[float],
        maxima: Sequence[float],
        target_size: int,
        names: Sequence[str],
    ) -> None:
        """Validate bounds and construct one regular axis per parameter."""
        if len(minima) == 0:
            raise ValueError("A parameter grid needs at least one dimension")
        if len(minima) != len(maxima) or len(minima) != len(names):
            raise ValueError("minima, maxima, and names must have the same length")
        if target_size <= 0:
            raise ValueError("target_size must be strictly positive")

        self.names = tuple(names)
        steps_per_axis = ceil(target_size ** (1 / len(minima)))
        self.axes = tuple(
            np.asarray(subdivide_interval(lower, upper, steps_per_axis), dtype=float)
            for lower, upper in zip(minima, maxima, strict=True)
        )

    @property
    def shape(self) -> tuple[int, ...]:
        """Number of sampled values along each parameter axis."""
        return tuple(len(axis) for axis in self.axes)

    @property
    def size(self) -> int:
        """Actual number of parameter combinations in the grid."""
        return int(np.prod(self.shape))

    def points(self) -> npt.NDArray[np.float64]:
        """Return parameter combinations with the last axis varying fastest."""
        return np.asarray(tuple(product(*self.axes)), dtype=float)

    def reshape(
        self,
        values: Sequence[float] | npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Reshape one value per parameter combination onto the grid axes."""
        array = np.asarray(values, dtype=float)
        if array.size != self.size:
            raise ValueError(f"Expected {self.size} grid values, received {array.size}")
        return array.reshape(self.shape)


__all__ = ["ParameterGrid"]
