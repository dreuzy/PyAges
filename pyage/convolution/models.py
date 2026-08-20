"""Shared value objects and errors for tracer/LPM convolution."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class PreparedTracerGrid:
    """Tracer-response samples cached for one observation date."""

    date: float
    edges: npt.NDArray[np.float64]
    k_left: npt.NDArray[np.float64]
    k_mid: npt.NDArray[np.float64]
    k_right: npt.NDArray[np.float64]

    @property
    def midpoints(self) -> npt.NDArray[np.float64]:
        """Return bin midpoints without storing redundant state."""
        return 0.5 * (self.edges[:-1] + self.edges[1:])


@dataclass(frozen=True)
class ConvolutionDiagnostics:
    """Cheap diagnostics from the latest continuous or mixed convolution."""

    window_mass: float
    n_bins: int
    min_weight: float
    clipped_weight_count: int


class ConvolutionError(Exception):
    """Exception raised for convolution preparation/execution errors."""
