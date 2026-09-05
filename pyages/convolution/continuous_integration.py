# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file combines a prepared tracer-response grid with the cumulative mass
# and first moment of a continuous water-age model. It returns one predicted
# concentration plus diagnostics, while probability older than the known tracer
# history remains unnormalized and therefore contributes zero.

"""Integrate continuous LPM laws on a prepared tracer-response grid.

The implementation uses exact CDF bin masses and partial first moments; it
never samples an LPM probability density or renormalizes the finite age window.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from pyages.convolution.errors import ConvolutionError
from pyages.convolution.settings import ConvolutionSettings
from pyages.convolution.tracer_grid import PreparedTracerGrid


@dataclass(frozen=True)
class ConvolutionDiagnostics:
    """Diagnostics from the latest continuous or mixed convolution.

    The integration kernel creates this record together with its concentration
    result. Mixed convolutions then adjust it to describe the complete mixture.

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


def _evaluate_moments(
    provider: Callable[
        [npt.NDArray[np.float64]],
        tuple[npt.ArrayLike, npt.ArrayLike],
    ],
    edges: npt.NDArray[np.float64],
    distribution_name: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Evaluate the vectorized CDF/partial-moment numerical contract.

    A provider must return one finite CDF value and one finite raw partial first
    moment for every requested edge. Shape checks here keep broadcasting errors
    from silently corrupting all later bin calculations.
    """
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
    if first_moment_edges.shape != edges.shape or not np.all(
        np.isfinite(first_moment_edges)
    ):
        raise ConvolutionError(
            f"LPM '{distribution_name}' returned invalid partial first moments"
        )
    return f_edges, first_moment_edges


def _bin_weights(
    f_edges: npt.NDArray[np.float64],
    distribution_name: str,
    settings: ConvolutionSettings,
) -> tuple[npt.NDArray[np.float64], ConvolutionDiagnostics]:
    """Turn edge CDF values into validated, non-negative bin masses.

    Only deviations compatible with floating-point round-off are clipped.
    Materially out-of-range or decreasing CDF values are model errors. The
    returned weights retain the original finite-window mass; they do not sum to
    one when part of the LPM lies outside the tracer record.
    """
    cdf_scale = max(1.0, float(np.max(np.abs(f_edges))))
    floating_tolerance = (
        settings.floating_weight_epsilon_factor * np.finfo(float).eps * cdf_scale
    )
    if np.any(f_edges < -floating_tolerance) or np.any(
        f_edges > 1.0 + floating_tolerance
    ):
        raise ConvolutionError(
            f"LPM '{distribution_name}' CDF returned values outside [0, 1]"
        )

    # The preceding bounds check guarantees that clipping removes round-off
    # only, rather than hiding an invalid CDF implementation.
    bounded_cdf = np.clip(f_edges, 0.0, 1.0)
    # CDF differences are exact probability masses for the prepared age bins.
    weights = np.diff(bounded_cdf)
    min_weight = float(np.min(weights)) if weights.size else 0.0
    if np.any(weights < -floating_tolerance):
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
        window_mass=float(bounded_cdf[-1] - bounded_cdf[0]),
        n_bins=int(weights.size),
        min_weight=min_weight,
        clipped_weight_count=clipped_count,
    )
    return weights, diagnostics


def window_mass_from_provider(
    provider: Callable[
        [npt.NDArray[np.float64]],
        tuple[npt.ArrayLike, npt.ArrayLike],
    ],
    upper_age: float,
    distribution_name: str,
    settings: ConvolutionSettings,
) -> float:
    """Return finite-window mass using the production integration contract.

    The partial moments are deliberately validated too, even though only the
    CDF is needed for the mass. Thus :meth:`Convolution.window_mass` cannot
    accept a provider that the full continuous convolution would reject.
    """
    edges = np.array([0.0, upper_age], dtype=float)
    f_edges, first_moment_edges = _evaluate_moments(
        provider,
        edges,
        distribution_name,
    )
    weights, diagnostics = _bin_weights(f_edges, distribution_name, settings)
    _centered_moments(
        first_moment_edges,
        edges,
        weights,
        distribution_name,
        settings,
    )
    return diagnostics.window_mass


def _centered_moments(
    first_moment_edges: npt.NDArray[np.float64],
    edges: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    distribution_name: str,
    settings: ConvolutionSettings,
) -> npt.NDArray[np.float64]:
    r"""Return first moments centered on each bin's left edge.

    For a bin ``[a, b]`` with mass :math:`w`, the centered moment is
    :math:`E[(T-a)1(a<T\leq b)]`; it must lie between zero and
    :math:`(b-a)w`. This bound detects inconsistent LPM moment providers before
    those values are multiplied by tracer-response slopes.
    """
    widths = np.diff(edges)
    centered = np.diff(first_moment_edges) - edges[:-1] * weights
    centered_upper = widths * weights
    tolerance = (
        settings.floating_weight_epsilon_factor
        * np.finfo(float).eps
        * max(1.0, float(edges[-1]))
    )
    if np.any(centered < -tolerance) or np.any(centered > centered_upper + tolerance):
        raise ConvolutionError(
            f"LPM '{distribution_name}' returned inconsistent partial first moments"
        )
    return np.clip(centered, 0.0, centered_upper)


def _integrate_response(
    grid: PreparedTracerGrid,
    weights: npt.NDArray[np.float64],
    centered_moments: npt.NDArray[np.float64],
    settings: ConvolutionSettings,
) -> float:
    """Combine exact bin masses with a local tracer-response approximation.

    The affine formula uses the exact mass and centered first moment, so it is
    exact whenever the response is linear inside a bin. If the stored midpoint
    reveals too much curvature for that affine model, the configured midpoint
    contribution is used for that bin instead.
    """
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
    # Curvature is a property of K, not of the LPM. The fallback therefore
    # remains valid when the same prepared grid is reused for another LPM.
    linear_contributions = np.where(
        curvature <= curvature_tolerance,
        linear_contributions,
        grid.k_mid * weights,
    )
    return float(np.sum(linear_contributions))


def convolve_prepared_grid(
    grid: PreparedTracerGrid,
    provider: Callable[
        [npt.NDArray[np.float64]],
        tuple[npt.ArrayLike, npt.ArrayLike],
    ],
    distribution_name: str,
    settings: ConvolutionSettings,
) -> tuple[float, ConvolutionDiagnostics]:
    r"""Integrate a continuous LPM over a prepared tracer-response grid.

    For bin :math:`[a_i,b_i]`, the provider supplies the CDF :math:`F` and raw
    partial first moment :math:`M(t)=E[T\,1(T\leq t)]`. PyAges forms

    .. math::

       w_i=F(b_i)-F(a_i),\qquad
       q_i=M(b_i)-M(a_i)-a_iw_i,

    then integrates the affine response as

    .. math::

       C_i=K(a_i)w_i+s_iq_i.

    This is exact for the piecewise-affine representation of ``K`` regardless
    of PDF width. Bins with excessive midpoint curvature instead use
    ``K(midpoint) * w_i``.

    Parameters
    ----------
    grid : PreparedTracerGrid
        Age grid and tracer responses; ages are in years.
    provider : callable
        Vectorized callable returning ``(F(t), M(t))`` at all grid edges.
    distribution_name : str
        Name included in numerical-contract errors.
    settings : ConvolutionSettings
        Curvature and floating-point consistency controls.

    Returns
    -------
    tuple of float and ConvolutionDiagnostics
        Concentration in the tracer's unit and diagnostics for the represented
        probability mass.

    Notes
    -----
    The integration window is closed and finite. Probability outside it is
    omitted, not renormalized; inspect ``diagnostics.window_mass`` when old
    tails may extend before the recharge record. See
    ``docs/scientific-methods.md`` for the model-level convention.
    """
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
