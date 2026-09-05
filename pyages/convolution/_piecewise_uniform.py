# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Precompute tracer responses for piecewise-uniform water-age models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from pyages.convolution.continuous_integration import (
    ConvolutionDiagnostics,
    _bin_weights,
    convolve_prepared_grid,
)
from pyages.convolution.errors import ConvolutionError
from pyages.convolution.settings import ConvolutionSettings
from pyages.convolution.tracer_grid import PreparedTracerGrid


def _validated_fractions(
    values: npt.ArrayLike,
    bin_count: int,
    distribution_name: str,
) -> np.ndarray:
    """Return finite non-negative masses closing to one within round-off."""
    fractions = np.asarray(values, dtype=float)
    if fractions.shape != (bin_count,) or not np.all(np.isfinite(fractions)):
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{distribution_name}' must return one "
            "finite fraction per bin"
        )
    tolerance = 64.0 * np.finfo(float).eps * max(1, fractions.size)
    if np.any(fractions < -tolerance) or not np.isclose(
        float(np.sum(fractions)),
        1.0,
        rtol=0.0,
        atol=tolerance,
    ):
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{distribution_name}' fractions must be "
            "non-negative and sum to one"
        )
    # Remove only round-off-sized negative mass. Material violations were
    # rejected above, and no normalization hides an invalid total.
    return np.clip(fractions, 0.0, None)


def piecewise_uniform_state(lpm: object) -> tuple[np.ndarray, np.ndarray]:
    """Return validated bin edges and masses from a declared model."""
    name = str(getattr(lpm, "name", type(lpm).__name__))
    edges_provider = getattr(lpm, "bin_edges", None)
    fractions_provider = getattr(lpm, "fractions", None)
    if not callable(edges_provider) or not callable(fractions_provider):
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{name}' must implement bin_edges() and fractions()"
        )
    try:
        edges = np.asarray(edges_provider(), dtype=float)
        fractions = np.asarray(fractions_provider(), dtype=float)
    except (TypeError, ValueError) as exc:
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{name}' returned invalid bins or fractions"
        ) from exc
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or edges[0] != 0.0
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{name}' must return finite, increasing "
            "bin edges beginning at zero"
        )
    return edges, _validated_fractions(fractions, edges.size - 1, name)


def _unit_bin_moments(
    ages: npt.NDArray[np.float64],
    left: float,
    right: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return CDF and partial first moment for one unit-mass uniform bin."""
    values = np.asarray(ages, dtype=float)
    width = right - left
    upper = np.clip(values, left, right)
    represented = values > left
    cdf = np.where(represented, (upper - left) / width, 0.0)
    first_moment = np.where(
        represented,
        (upper**2 - left**2) / (2.0 * width),
        0.0,
    )
    return cdf, first_moment


@dataclass(frozen=True, slots=True)
class PreparedPiecewiseUniformBasis:
    """Immutable per-bin tracer responses for one prepared tracer grid."""

    bin_edges: npt.NDArray[np.float64]
    responses: npt.NDArray[np.float64]
    cdf_at_grid_edges: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        """Validate dimensions and detach all cached arrays from their owners."""
        edges = np.array(self.bin_edges, dtype=float, copy=True)
        responses = np.array(self.responses, dtype=float, copy=True)
        cdf = np.array(self.cdf_at_grid_edges, dtype=float, copy=True)
        bin_count = edges.size - 1
        if (
            edges.ndim != 1
            or edges.size < 2
            or not np.all(np.isfinite(edges))
            or edges[0] != 0.0
            or np.any(np.diff(edges) <= 0.0)
        ):
            raise ValueError(
                "PreparedPiecewiseUniformBasis.bin_edges must be finite, "
                "increasing, and begin at zero"
            )
        if responses.shape != (bin_count,) or not np.all(np.isfinite(responses)):
            raise ValueError(
                "PreparedPiecewiseUniformBasis.responses must contain one finite "
                "value per bin"
            )
        if (
            cdf.ndim != 2
            or cdf.shape[0] != bin_count
            or cdf.shape[1] < 1
            or not np.all(np.isfinite(cdf))
            or np.any(cdf < 0.0)
            or np.any(cdf > 1.0)
            or np.any(np.diff(cdf, axis=1) < 0.0)
        ):
            raise ValueError(
                "PreparedPiecewiseUniformBasis.cdf_at_grid_edges has invalid "
                "shape or cumulative probabilities"
            )
        for name, values in (
            ("bin_edges", edges),
            ("responses", responses),
            ("cdf_at_grid_edges", cdf),
        ):
            values.setflags(write=False)
            object.__setattr__(self, name, values)

    def matches(self, bin_edges: npt.ArrayLike) -> bool:
        """Return whether this basis represents exactly the supplied geometry."""
        candidate = np.asarray(bin_edges, dtype=float)
        return candidate.shape == self.bin_edges.shape and np.array_equal(
            candidate,
            self.bin_edges,
        )

    def convolve(
        self,
        fractions: npt.ArrayLike,
        distribution_name: str,
        settings: ConvolutionSettings,
    ) -> tuple[float, ConvolutionDiagnostics]:
        """Combine cached bin responses and reconstruct standard diagnostics."""
        weights = _validated_fractions(
            fractions,
            self.responses.size,
            distribution_name,
        )
        combined_cdf = weights @ self.cdf_at_grid_edges
        _, diagnostics = _bin_weights(combined_cdf, distribution_name, settings)
        result = float(np.dot(weights, self.responses))
        if not np.isfinite(result):
            raise ConvolutionError(
                f"Piecewise-uniform LPM '{distribution_name}' produced a "
                "non-finite cached convolution"
            )
        return result, diagnostics


def prepare_piecewise_uniform_basis(
    grid: PreparedTracerGrid,
    bin_edges: npt.ArrayLike,
    distribution_name: str,
    settings: ConvolutionSettings,
) -> PreparedPiecewiseUniformBasis:
    """Integrate every unit-mass age bin once on a prepared tracer grid."""
    edges = np.asarray(bin_edges, dtype=float)
    if (
        edges.ndim != 1
        or edges.size < 2
        or not np.all(np.isfinite(edges))
        or edges[0] != 0.0
        or np.any(np.diff(edges) <= 0.0)
    ):
        raise ConvolutionError(
            f"Piecewise-uniform LPM '{distribution_name}' returned invalid bin edges"
        )

    responses: list[float] = []
    cdf_rows: list[np.ndarray] = []
    for index, (left, right) in enumerate(
        zip(edges[:-1], edges[1:], strict=True),
        start=1,
    ):

        def provider(
            ages: npt.NDArray[np.float64],
            lo: float = left,
            hi: float = right,
        ) -> tuple[np.ndarray, np.ndarray]:
            return _unit_bin_moments(ages, lo, hi)

        cdf, _first_moment = provider(grid.edges)
        cdf_rows.append(np.asarray(cdf, dtype=float))
        if grid.edges.size == 1:
            responses.append(0.0)
            continue
        response, _diagnostics = convolve_prepared_grid(
            grid,
            provider,
            f"{distribution_name} bin {index}",
            settings,
        )
        responses.append(response)

    return PreparedPiecewiseUniformBasis(
        bin_edges=edges,
        responses=np.asarray(responses, dtype=float),
        cdf_at_grid_edges=np.vstack(cdf_rows),
    )


__all__: list[str] = []
