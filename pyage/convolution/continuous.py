"""Numerical details for continuous tracer/LPM convolution."""

from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from pyage.convolution.models import (
    ConvolutionDiagnostics,
    ConvolutionError,
    PreparedTracerGrid,
)
from pyage.convolution.settings import TracerGridSettings


Array = npt.NDArray[np.float64]
TracerEvaluator = Callable[[npt.ArrayLike], Array]
MomentProvider = Callable[[Array], tuple[npt.ArrayLike, npt.ArrayLike]]


def prepare_adaptive_grid(
    *,
    date: float,
    initial_edges: Array,
    edge_values: Array,
    right_edge_values: Array,
    evaluate: TracerEvaluator,
    settings: TracerGridSettings,
) -> PreparedTracerGrid:
    """Refine tracer bins until their response is locally resolved."""
    active_left = initial_edges[:-1]
    active_right = initial_edges[1:]
    active_k_left = edge_values[:-1]
    active_k_right = right_edge_values
    active_depth = np.zeros(active_left.size, dtype=np.int16)
    accepted: list[tuple[float, float, float, float, float]] = []
    global_scale = max(
        float(np.max(np.abs(active_k_left))),
        float(np.max(np.abs(active_k_right))),
    )

    while active_left.size:
        midpoints = 0.5 * (active_left + active_right)
        k_mid = evaluate(midpoints)
        global_scale = max(global_scale, float(np.max(np.abs(k_mid))))
        k_range = np.maximum.reduce(
            (active_k_left, k_mid, active_k_right)
        ) - np.minimum.reduce((active_k_left, k_mid, active_k_right))
        local_scale = np.maximum.reduce(
            (np.abs(active_k_left), np.abs(k_mid), np.abs(active_k_right))
        )
        k_atol = settings.absolute_tolerance_factor * max(
            global_scale, np.finfo(float).eps
        )
        accept_mask = (
            k_range <= k_atol + settings.relative_tolerance * local_scale
        )

        for index in np.flatnonzero(accept_mask):
            accepted.append(
                (
                    float(active_left[index]),
                    float(active_right[index]),
                    float(active_k_left[index]),
                    float(k_mid[index]),
                    float(active_k_right[index]),
                )
            )

        split_mask = ~accept_mask
        if not np.any(split_mask):
            break
        if np.any(active_depth[split_mask] >= settings.max_subdivisions):
            worst = float(np.max(k_range[split_mask]))
            raise ConvolutionError(
                "Tracer-grid refinement did not converge within "
                f"{settings.max_subdivisions} subdivisions "
                f"(largest remaining K range={worst:.6g})"
            )

        split_count = int(np.count_nonzero(split_mask))
        if len(accepted) + 2 * split_count > settings.max_bins:
            raise ConvolutionError(
                "Tracer-grid refinement exceeded "
                f"grid_settings.max_bins={settings.max_bins}"
            )

        left = active_left[split_mask]
        right = active_right[split_mask]
        middle = midpoints[split_mask]
        k_left = active_k_left[split_mask]
        k_right = active_k_right[split_mask]
        k_middle = k_mid[split_mask]
        depth = active_depth[split_mask] + 1
        active_left = np.concatenate((left, middle))
        active_right = np.concatenate((middle, right))
        active_k_left = np.concatenate((k_left, k_middle))
        active_k_right = np.concatenate((k_middle, k_right))
        active_depth = np.concatenate((depth, depth))

    accepted.sort(key=lambda interval: interval[0])
    if len(accepted) > settings.max_bins:
        raise ConvolutionError(
            f"Prepared tracer grid has {len(accepted)} bins, exceeding "
            f"grid_settings.max_bins={settings.max_bins}"
        )
    accepted_array = np.asarray(accepted, dtype=float)
    edges = np.concatenate((accepted_array[:, 0], accepted_array[-1:, 1]))
    return PreparedTracerGrid(
        date=date,
        edges=edges,
        k_left=accepted_array[:, 2],
        k_mid=accepted_array[:, 3],
        k_right=accepted_array[:, 4],
    )


def _evaluate_moments(
    provider: MomentProvider,
    edges: Array,
    distribution_name: str,
) -> tuple[Array, Array]:
    """Evaluate and validate vectorized CDF and partial moments."""
    try:
        f_edges, first_moment_edges = provider(edges)
    except NotImplementedError as exc:
        raise ConvolutionError(
            f"Continuous LPM '{distribution_name}' must implement "
            "cdf_and_partial_first_moment()"
        ) from exc
    f_edges = np.asarray(f_edges, dtype=float)
    first_moment_edges = np.asarray(first_moment_edges, dtype=float)
    if f_edges.shape != edges.shape:
        raise ConvolutionError(
            f"LPM '{distribution_name}' CDF is not vectorized: returned shape "
            f"{f_edges.shape}, expected {edges.shape}"
        )
    if not np.all(np.isfinite(f_edges)):
        raise ConvolutionError(
            f"LPM '{distribution_name}' CDF returned non-finite values"
        )
    if (
        first_moment_edges.shape != edges.shape
        or not np.all(np.isfinite(first_moment_edges))
    ):
        raise ConvolutionError(
            f"LPM '{distribution_name}' returned invalid partial first moments"
        )
    return f_edges, first_moment_edges


def _bin_weights(
    f_edges: Array,
    distribution_name: str,
    settings: TracerGridSettings,
) -> tuple[Array, ConvolutionDiagnostics]:
    """Derive non-negative bin masses and their diagnostics from a CDF."""
    weights = np.diff(f_edges)
    min_weight = float(np.min(weights)) if weights.size else 0.0
    cdf_scale = max(1.0, float(np.max(np.abs(f_edges))))
    negative_tolerance = (
        settings.floating_weight_epsilon_factor
        * np.finfo(float).eps
        * cdf_scale
    )
    if np.any(weights < -negative_tolerance):
        raise ConvolutionError(
            f"LPM '{distribution_name}' CDF is not monotonic on the tracer grid; "
            f"minimum bin mass is {min_weight:.6g}"
        )
    negative_mask = weights < 0.0
    clipped_count = int(np.count_nonzero(negative_mask))
    if clipped_count:
        weights = weights.copy()
        weights[negative_mask] = 0.0
    diagnostics = ConvolutionDiagnostics(
        window_mass=float(f_edges[-1] - f_edges[0]),
        n_bins=int(weights.size),
        min_weight=min_weight,
        clipped_weight_count=clipped_count,
    )
    return weights, diagnostics


def _centered_moments(
    first_moment_edges: Array,
    edges: Array,
    weights: Array,
    distribution_name: str,
    settings: TracerGridSettings,
) -> Array:
    """Validate first moments after translating each bin to its left edge."""
    widths = np.diff(edges)
    centered = np.diff(first_moment_edges) - edges[:-1] * weights
    centered_upper = widths * weights
    tolerance = (
        settings.floating_weight_epsilon_factor
        * np.finfo(float).eps
        * max(1.0, float(edges[-1]))
    )
    if np.any(centered < -tolerance) or np.any(
        centered > centered_upper + tolerance
    ):
        raise ConvolutionError(
            f"LPM '{distribution_name}' returned inconsistent partial first moments"
        )
    return np.clip(centered, 0.0, centered_upper)


def _integrate_response(
    grid: PreparedTracerGrid,
    weights: Array,
    centered_moments: Array,
    settings: TracerGridSettings,
) -> float:
    """Combine exact bin masses with a locally linear tracer response."""
    widths = np.diff(grid.edges)
    slopes = (grid.k_right - grid.k_left) / widths
    linear_contributions = grid.k_left * weights + slopes * centered_moments
    global_scale = max(
        float(np.max(np.abs(grid.k_left))),
        float(np.max(np.abs(grid.k_mid))),
        float(np.max(np.abs(grid.k_right))),
        np.finfo(float).eps,
    )
    local_scale = np.maximum.reduce(
        (np.abs(grid.k_left), np.abs(grid.k_mid), np.abs(grid.k_right))
    )
    curvature = np.abs(grid.k_mid - 0.5 * (grid.k_left + grid.k_right))
    curvature_tolerance = settings.linear_curvature_factor * (
        settings.absolute_tolerance_factor * global_scale
        + settings.relative_tolerance * local_scale
    )
    linear_contributions = np.where(
        curvature <= curvature_tolerance,
        linear_contributions,
        grid.k_mid * weights,
    )
    return float(np.sum(linear_contributions))


def convolve_prepared_grid(
    grid: PreparedTracerGrid,
    provider: MomentProvider,
    distribution_name: str,
    settings: TracerGridSettings,
) -> tuple[float, ConvolutionDiagnostics]:
    """Convolve one continuous distribution on a prepared tracer grid."""
    f_edges, first_moment_edges = _evaluate_moments(
        provider, grid.edges, distribution_name
    )
    weights, diagnostics = _bin_weights(f_edges, distribution_name, settings)
    moments = _centered_moments(
        first_moment_edges,
        grid.edges,
        weights,
        distribution_name,
        settings,
    )
    return _integrate_response(grid, weights, moments, settings), diagnostics
