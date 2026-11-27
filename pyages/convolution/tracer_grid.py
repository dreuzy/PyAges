# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file turns a tracer history and observation date into reusable response
# samples indexed by water age. It refines intervals where the tracer changes
# rapidly and returns immutable arrays consumed by continuous convolution; the
# grid is independent of the water-age model and can be reused during calibration.

"""Build reusable adaptive samples of a tracer response over water age.

Grid refinement depends only on the tracer, observation date, and settings—not
on an LPM—so one prepared grid can serve many distributions during calibration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from pyages.convolution.errors import ConvolutionError
from pyages.convolution.settings import ConvolutionSettings
from pyages.tracer.protocols import ConvolutionTracerProtocol


@dataclass(frozen=True)
class PreparedTracerGrid:
    """Immutable tracer-response samples cached for one observation date.

    This is the validated output of :func:`prepare_tracer_grid`. Keeping the
    record beside its builder makes the grid topology and its construction
    contract explicit in one module.

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


def evaluate_tracer_response(
    tracer: ConvolutionTracerProtocol,
    date: float,
    ages: npt.ArrayLike,
) -> npt.NDArray[np.float64]:
    """Evaluate the complete tracer response on a vectorized age grid.

    ``get_concentration`` receives both recharge date ``date - age`` and age,
    allowing tracer-specific decay or production to remain part of the sampled
    response. Scalar tracer implementations are broadcast deliberately; every
    other result must match the requested grid shape and contain finite values.
    """
    ages_array = np.asarray(ages, dtype=float)
    values = np.asarray(
        tracer.get_concentration(date - ages_array, ages_array),
        dtype=float,
    )
    if values.ndim == 0:
        values = np.full(ages_array.shape, float(values), dtype=float)
    else:
        try:
            values = np.asarray(np.broadcast_to(values, ages_array.shape), dtype=float)
        except ValueError as exc:
            raise ConvolutionError(
                "Tracer response shape does not match the requested age grid: "
                f"{values.shape} versus {ages_array.shape}"
            ) from exc
    if not np.all(np.isfinite(values)):
        raise ConvolutionError("Tracer response contains non-finite values")
    return values


def _initial_age_edges(
    tracer: ConvolutionTracerProtocol,
    date: float,
    upper_age: float,
    settings: ConvolutionSettings,
) -> npt.NDArray[np.float64]:
    """Seed age-bin edges from known chronicle nodes or a bounded fallback."""
    if upper_age == 0.0:
        return np.array([0.0], dtype=float)

    edges = np.array([0.0, upper_age], dtype=float)
    dates = tracer.convolution_dates
    if dates is not None:
        # Chronicle dates become ages because the integration coordinate is
        # transit time. Keeping interior knots prevents refinement from
        # smoothing across known changes in the input history.
        dates_array = np.asarray(dates, dtype=float).reshape(-1)
        ages = date - dates_array
        ages = ages[np.isfinite(ages) & (ages > 0.0) & (ages < upper_age)]
        if ages.size:
            edges = np.concatenate((edges, ages))
    else:
        initial_bins = int(tracer.convolution_initial_bins)
        if initial_bins < 1:
            raise ConvolutionError("tracer.convolution_initial_bins must be at least 1")
        if initial_bins > settings.max_bins:
            raise ConvolutionError(
                "tracer.convolution_initial_bins exceeds "
                f"grid_settings.max_bins={settings.max_bins}"
            )
        edges = np.linspace(0.0, upper_age, initial_bins + 1)

    edges = np.unique(edges)
    if edges.size - 1 > settings.max_bins:
        raise ConvolutionError(
            f"Initial tracer grid has {edges.size - 1} bins, exceeding "
            f"grid_settings.max_bins={settings.max_bins}"
        )
    return edges


def _right_edge_values(
    tracer: ConvolutionTracerProtocol,
    date: float,
    initial_edges: npt.NDArray[np.float64],
    edge_values: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Use the correct one-sided value at the newest chronicle boundary.

    At age ``date - datemax``, evaluation exactly on ``datemax`` may return the
    first in-record value. For the younger bin ending at that boundary, however,
    the response must approach from dates newer than ``datemax``. Sampling one
    floating-point step outside the record preserves that possible jump.
    """
    values = edge_values[1:].copy()
    boundary_dates = tracer.convolution_dates
    has_newest_boundary = boundary_dates is not None and np.any(
        np.asarray(boundary_dates, dtype=float) == float(tracer.datemax)
    )
    newest_boundary_age = float(date - tracer.datemax)
    if not has_newest_boundary or not 0.0 < newest_boundary_age < initial_edges[-1]:
        return values

    outside_bins = np.flatnonzero(initial_edges[1:] == newest_boundary_age)
    if outside_bins.size:
        # ``nextafter`` asks the tracer for the nearest representable date on
        # the outside of the boundary without introducing an arbitrary offset.
        outside_date = np.nextafter(float(tracer.datemax), np.inf)
        outside_age = float(date - outside_date)
        outside_value = evaluate_tracer_response(
            tracer,
            date,
            np.array([outside_age], dtype=float),
        )[0]
        values[outside_bins] = outside_value
    return values


def _refine_adaptive_grid(
    *,
    date: float,
    initial_edges: npt.NDArray[np.float64],
    edge_values: npt.NDArray[np.float64],
    right_edge_values: npt.NDArray[np.float64],
    evaluate: Callable[[npt.ArrayLike], npt.NDArray[np.float64]],
    settings: ConvolutionSettings,
) -> PreparedTracerGrid:
    r"""Bisect age bins until the tracer response is locally resolved.

    For each age interval :math:`[a,b]`, the routine evaluates the complete
    tracer response :math:`K` at ``a``, ``(a+b)/2``, and ``b``. It accepts the
    interval using the mixed global/local criterion documented by
    :class:`~pyages.convolution.settings.ConvolutionSettings`; otherwise it
    bisects the interval. Initial edges should therefore include known
    chronicle knots and discontinuities.

    The acceptance criterion resolves response amplitude, not quadrature error
    directly. Publication runs using non-default tolerances require a
    convergence or sensitivity check.
    """
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
        # ``active_*`` is the current refinement frontier. Accepted bins leave
        # the frontier permanently; rejected bins are replaced by two children.
        midpoints = 0.5 * (active_left + active_right)
        k_mid = evaluate(midpoints)
        # The scale only grows. Bins visited before the largest response is
        # found may therefore be refined more strictly, never more loosely.
        global_scale = max(global_scale, float(np.max(np.abs(k_mid))))
        k_range = np.maximum.reduce(
            (active_k_left, k_mid, active_k_right)
        ) - np.minimum.reduce((active_k_left, k_mid, active_k_right))
        local_scale = np.maximum.reduce(
            (np.abs(active_k_left), np.abs(k_mid), np.abs(active_k_right))
        )
        k_atol = settings.absolute_tolerance_factor * max(
            global_scale,
            np.finfo(float).eps,
        )
        accept_mask = k_range <= k_atol + settings.relative_tolerance * local_scale

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
        # Reuse each evaluated midpoint as the shared child boundary; this is
        # both cheaper and numerically consistent with the acceptance test.
        active_left = np.concatenate((left, middle))
        active_right = np.concatenate((middle, right))
        active_k_left = np.concatenate((k_left, k_middle))
        active_k_right = np.concatenate((k_middle, k_right))
        active_depth = np.concatenate((depth, depth))

    # Vectorized bisection does not preserve spatial order, so sort before
    # rebuilding the single contiguous edge vector required downstream.
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


def prepare_tracer_grid(
    tracer: ConvolutionTracerProtocol,
    date: float,
    upper_age: float,
    settings: ConvolutionSettings,
) -> PreparedTracerGrid:
    """Build a validated, immutable tracer-only grid for one observation date.

    The finite integration domain is ``[0, upper_age]``. A zero-width domain is
    represented by one edge and no bins; otherwise initial tracer knots are
    refined until every bin meets the response criterion or a safety limit
    raises :class:`ConvolutionError`.
    """
    if not np.isfinite(upper_age) or upper_age < 0.0:
        raise ConvolutionError(f"Invalid tracer-grid upper age {upper_age!r}")

    initial_edges = _initial_age_edges(tracer, date, upper_age, settings)
    if initial_edges.size == 1:
        empty = np.array([], dtype=float)
        return PreparedTracerGrid(
            date=date,
            edges=initial_edges,
            k_left=empty,
            k_mid=empty,
            k_right=empty,
        )

    def evaluate(ages: npt.ArrayLike) -> npt.NDArray[np.float64]:
        return evaluate_tracer_response(tracer, date, ages)

    edge_values = evaluate(initial_edges)
    right_edge_values = _right_edge_values(
        tracer,
        date,
        initial_edges,
        edge_values,
    )
    return _refine_adaptive_grid(
        date=date,
        initial_edges=initial_edges,
        edge_values=edge_values,
        right_edge_values=right_edge_values,
        evaluate=evaluate,
        settings=settings,
    )


__all__ = [
    "PreparedTracerGrid",
    "evaluate_tracer_response",
    "prepare_tracer_grid",
]
