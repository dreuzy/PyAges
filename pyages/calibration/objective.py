# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file computes the residual measures minimized during calibration.

"""Define residual objectives and comparison metrics for calibration.

The historical PyAges objective is the sum of squared residuals divided by
observation uncertainty.  It remains available through
:func:`squared_normalized_residuals` and is the fixed Gaussian target used by
the posterior sampler.

Deterministic inversion can additionally combine an L1 or squared-L2 loss with
absolute, relative, or uncertainty scaling through :class:`ObjectiveSpec`.
Comparison metrics are evaluated independently of the objective that selected
the solution, allowing one fitted state to be inspected under both L1 and L2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

LossName = Literal["l1", "l2"]
ResidualScale = Literal["absolute", "relative", "uncertainty"]


def _validated_relative_floor(value: float) -> float:
    """Return one finite positive relative-residual denominator floor."""
    if isinstance(value, bool):
        raise ValueError("relative_floor must be finite and strictly positive")
    try:
        floor = float(value)
    except (TypeError, ValueError, OverflowError) as exception:
        raise ValueError(
            "relative_floor must be finite and strictly positive"
        ) from exception
    if not np.isfinite(floor) or floor <= 0.0:
        raise ValueError("relative_floor must be finite and strictly positive")
    return floor


def _as_arrays(
    data: npt.ArrayLike,
    model: npt.ArrayLike,
    error: npt.ArrayLike,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert residual inputs to equal-shaped arrays.

    A scalar uncertainty is broadcast to the observation shape. Dimensionality,
    emptiness, finiteness, and scale-specific constraints are checked by the
    caller so this helper can also support the historical residual functions.
    """
    data_arr = np.asarray(data, dtype=float)
    model_arr = np.asarray(model, dtype=float)
    error_arr = np.asarray(error, dtype=float)

    if error_arr.shape == () and data_arr.shape != ():
        error_arr = np.full_like(data_arr, float(error_arr))

    if data_arr.shape != model_arr.shape or data_arr.shape != error_arr.shape:
        raise ValueError(
            "data, model, and error must have the same shape "
            f"(got data={data_arr.shape}, model={model_arr.shape}, error={error_arr.shape})"
        )

    return data_arr, model_arr, error_arr


def _validated_residual_arrays(
    data: npt.ArrayLike,
    model: npt.ArrayLike,
    error: npt.ArrayLike,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return finite, non-empty, one-dimensional residual inputs."""
    data_arr, model_arr, error_arr = _as_arrays(data, model, error)
    if data_arr.ndim != 1:
        raise ValueError(
            f"Residual inputs must be one-dimensional (got shape {data_arr.shape})"
        )
    if data_arr.size == 0:
        raise ValueError("Residual inputs must contain at least one observation")
    if not (
        np.all(np.isfinite(data_arr))
        and np.all(np.isfinite(model_arr))
        and np.all(np.isfinite(error_arr))
    ):
        raise ValueError("Residual inputs must contain only finite values")
    return data_arr, model_arr, error_arr


def scaled_residuals(
    data: npt.ArrayLike,
    model: npt.ArrayLike,
    error: npt.ArrayLike,
    *,
    scale: ResidualScale,
    relative_floor: float = 1e-300,
) -> np.ndarray:
    r"""Return signed residuals on the requested comparison scale.

    Residuals always use the sign ``modeled - observed``. ``absolute`` retains
    the concentration units, ``relative`` divides by
    ``max(abs(observed), relative_floor)``, and ``uncertainty`` divides by the
    positive one-standard-deviation observation error.

    Parameters
    ----------
    data, model
        Equal-shaped, one-dimensional observed and modeled concentrations.
    error
        Observation uncertainties with the same shape, or one scalar to
        broadcast to every observation. Errors must be finite for every scale
        and strictly positive for ``uncertainty`` scaling.
    scale
        Denominator convention used to make the signed residuals comparable.
    relative_floor
        Smallest relative denominator. This prevents division by zero without
        changing observations whose absolute value exceeds the floor.

    Returns
    -------
    numpy.ndarray
        A new one-dimensional array in observation order.

    Raises
    ------
    ValueError
        If the scale is unknown or the input arrays cannot define finite,
        non-empty residuals on the requested scale.
    """
    if scale not in {"absolute", "relative", "uncertainty"}:
        raise ValueError(f"Unknown residual scale: {scale!r}")
    floor = _validated_relative_floor(relative_floor)

    data_arr, model_arr, error_arr = _validated_residual_arrays(data, model, error)
    residual = model_arr - data_arr
    if scale == "absolute":
        return residual
    if scale == "relative":
        denominator = np.maximum(np.abs(data_arr), floor)
        return residual / denominator
    if np.any(error_arr <= 0.0):
        raise ValueError(
            "Observation errors must be strictly positive for uncertainty scaling"
        )
    return residual / error_arr


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    r"""Describe one deterministic residual objective.

    ``loss='l1'`` evaluates :math:`\sum_i |r_i|`. ``loss='l2'`` evaluates
    :math:`\sum_i r_i^2`; the stored value is deliberately the sum of squares,
    not its square root. ``scale`` determines how the signed residuals are made
    comparable before aggregation. The frozen value object can therefore be
    recorded with an inversion result without hidden mutable optimizer state.

    Parameters
    ----------
    loss
        ``"l1"`` for the sum of absolute scaled residuals or ``"l2"`` for
        their sum of squares.
    scale
        ``"absolute"``, ``"relative"``, or ``"uncertainty"`` as defined by
        :func:`scaled_residuals`.
    relative_floor
        Strictly positive finite denominator floor used by relative scaling.
        It is retained in every specification for reproducible diagnostics.
    """

    loss: LossName = "l2"
    scale: ResidualScale = "uncertainty"
    relative_floor: float = 1e-300

    def __post_init__(self) -> None:
        """Reject unknown loss/scale names and unsafe relative floors."""
        if self.loss not in {"l1", "l2"}:
            raise ValueError(f"Unknown objective loss: {self.loss!r}")
        if self.scale not in {"absolute", "relative", "uncertainty"}:
            raise ValueError(f"Unknown residual scale: {self.scale!r}")
        _validated_relative_floor(self.relative_floor)

    @property
    def name(self) -> str:
        """Return the stable identifier recorded with inversion results."""
        return f"{self.scale}_{self.loss}"

    @classmethod
    def pyages_default(cls) -> ObjectiveSpec:
        """Return the historical uncertainty-weighted squared-L2 objective."""
        return cls(loss="l2", scale="uncertainty")

    @classmethod
    def relative_l1(cls, *, relative_floor: float = 1e-300) -> ObjectiveSpec:
        """Return the relative L1 objective used by the TracerLPM comparison."""
        return cls(loss="l1", scale="relative", relative_floor=relative_floor)

    @classmethod
    def relative_l2(cls, *, relative_floor: float = 1e-300) -> ObjectiveSpec:
        """Return the common relative squared-L2 comparison objective."""
        return cls(loss="l2", scale="relative", relative_floor=relative_floor)

    def evaluate(
        self,
        data: npt.ArrayLike,
        model: npt.ArrayLike,
        error: npt.ArrayLike,
    ) -> float:
        """Aggregate one modeled observation vector into a scalar objective.

        ``data``, ``model``, and ``error`` follow the validation and ordering
        rules of :func:`scaled_residuals`. The returned scalar is suitable for
        minimization; it does not modify any input array or LPM.
        """
        residual = scaled_residuals(
            data,
            model,
            error,
            scale=self.scale,
            relative_floor=self.relative_floor,
        )
        if self.loss == "l1":
            return float(np.sum(np.abs(residual)))
        return float(np.sum(np.square(residual)))

    def to_dict(self) -> dict[str, str | float]:
        """Return a detached JSON-compatible objective description."""
        return {
            "name": self.name,
            "loss": self.loss,
            "scale": self.scale,
            "relative_floor": float(self.relative_floor),
        }


def comparison_metrics(
    data: npt.ArrayLike,
    model: npt.ArrayLike,
    error: npt.ArrayLike,
    *,
    relative_floor: float = 1e-300,
) -> dict[str, float]:
    r"""Evaluate dimensionless L1/L2 diagnostics for one modeled state.

    Raw concentration residuals are intentionally not aggregated because one
    calibration can combine tracers expressed in different physical units.
    Let :math:`q_i=(m_i-y_i)/\max(|y_i|, f)` be the relative residual and
    :math:`z_i=(m_i-y_i)/\sigma_i` the uncertainty-standardized residual. The
    returned mapping contains, for both conventions, the L1 sum, mean absolute
    residual, squared-L2 sum, root mean square, and maximum absolute residual.
    The historical names ``chi_square`` (:math:`\sum z_i^2`) and
    ``normalized_residual_rms`` are retained for the standardized variants.

    These metrics describe the same fitted state independently of the
    :class:`ObjectiveSpec` that selected it; they never affect optimization.
    Input validation and scalar-error broadcasting match
    :func:`scaled_residuals`.
    """
    relative = scaled_residuals(
        data,
        model,
        error,
        scale="relative",
        relative_floor=relative_floor,
    )
    standardized = scaled_residuals(
        data,
        model,
        error,
        scale="uncertainty",
        relative_floor=relative_floor,
    )
    relative_squared = np.square(relative)
    standardized_squared = np.square(standardized)
    return {
        "relative_l1": float(np.sum(np.abs(relative))),
        "mean_absolute_relative_residual": float(np.mean(np.abs(relative))),
        "relative_l2_squared": float(np.sum(relative_squared)),
        "relative_rms": float(np.sqrt(np.mean(relative_squared))),
        "maximum_absolute_relative_residual": float(np.max(np.abs(relative))),
        "standardized_l1": float(np.sum(np.abs(standardized))),
        "mean_absolute_standardized_residual": float(np.mean(np.abs(standardized))),
        "chi_square": float(np.sum(standardized_squared)),
        "normalized_residual_rms": float(np.sqrt(np.mean(standardized_squared))),
        "maximum_absolute_standardized_residual": float(np.max(np.abs(standardized))),
    }


def squared_normalized_residuals(data, model, error):
    r"""Return independent Gaussian squared-normalized residuals.

    For observation :math:`y_i`, prediction :math:`m_i`, and reported
    one-standard-deviation uncertainty :math:`\sigma_i`, each contribution is
    :math:`r_i^2=((m_i-y_i)/\sigma_i)^2`. Their sum is the chi-square quantity
    used by :class:`~pyages.calibration.problem.CalibrationProblem`.

    Parameters
    ----------
    data : array-like
        Observed data values.
    model : array-like
        Modeled data values (same shape as data).
    error : array-like
        One-standard-deviation uncertainties in the same units and order as
        ``data``. Scientific calibration callers require finite positive
        values; this low-level vector operation only checks shapes.

    Returns
    -------
    numpy.ndarray
        Dimensionless squared normalized residuals, one per observation.

    Notes
    -----
    The likelihood assumes independent, unbiased Gaussian observation errors
    with known standard deviations. Correlated errors require a covariance
    likelihood and are not represented by this function.
    """
    data_arr, model_arr, error_arr = _as_arrays(data, model, error)
    return np.square((model_arr - data_arr) / error_arr)


def normalized_residual_norm(chi_square, sample_count):
    r"""Return :math:`\sqrt{\chi^2/n}` for normalized residuals.

    This diagnostic is dimensionless because residuals have already been
    divided by observation uncertainty; it is not an RMSE in concentration
    units.

    Parameters
    ----------
    chi_square : array-like or float
        Chi-square value or values, :math:`\chi^2=\sum_i r_i^2`.
    sample_count : int
        Number of residuals used in the sum; must be positive. No fitted-degree
        of-freedom correction is applied.

    Returns
    -------
    numpy.ndarray or float
        Dimensionless :math:`\sqrt{\chi^2/n}` value or values.
    """
    if sample_count <= 0:
        raise ValueError(f"sample_count must be positive (got {sample_count})")
    return np.sqrt(np.asarray(chi_square, dtype=float) / sample_count)


__all__ = [
    "LossName",
    "ObjectiveSpec",
    "ResidualScale",
    "comparison_metrics",
    "normalized_residual_norm",
    "scaled_residuals",
    "squared_normalized_residuals",
]
