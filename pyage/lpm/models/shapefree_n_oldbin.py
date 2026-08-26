# -*- coding: utf-8 -*-
"""
Piecewise-uniform shape-free LPM with a configurable old bin.

Purpose
-------
Represent a shape-free transit-time distribution as a set of age bins with a
stick-breaking parameterization. The last bin is an "old" age interval, but it
can be configured in two generic ways:

- ``bounded``: the last bin is a finite-width interval defined entirely in
  ``params.yaml``;
- ``support_open``: the last bin starts at the configured last edge and ends at
  the LPM-configured maximum support.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.special import expit

from pyage.config.paths import DIRECTORY_LPM_DATA
from pyage.data_io import lpm_params
from pyage.lpm.core.lpm_base import LpmBase
from pyage.lpm.core.registry import register_lpm

MODEL_NAME = "shapefree_n_oldbin"
VALID_MODES = {"bounded", "support_open"}


@dataclass(frozen=True)
class ShapeFreeSpec:
    """Parsed shape-free bin specification."""

    mode: str
    edges: np.ndarray
    support_end_max: float | None = None

    @property
    def n_bins(self) -> int:
        """Return the number of physical bins represented by the specification."""
        if self.mode == "support_open":
            return len(self.edges)
        return len(self.edges) - 1

    def effective_edges(self) -> np.ndarray:
        """Return finite bin edges for plotting, moments, or convolution."""
        if self.mode == "bounded":
            return self.edges.copy()

        support_end = self.support_end_max
        if support_end is None or not np.isfinite(support_end):
            raise ValueError(f"{MODEL_NAME}: invalid support end {support_end!r}")
        support_end = max(float(support_end), float(self.edges[-1]))
        return np.concatenate([self.edges, np.asarray([support_end], dtype=float)])


def _as_float_array(values: list[Any], *, field_name: str) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{MODEL_NAME}: invalid {field_name}: {values!r}") from exc
    if array.ndim != 1:
        raise ValueError(f"{MODEL_NAME}: {field_name} must be a 1D sequence")
    return array


def _load_model_spec(directory_lpm: str | Path | None) -> tuple[Path, dict[str, Any]]:
    resolved_dir = (
        Path(directory_lpm) if directory_lpm is not None else DIRECTORY_LPM_DATA
    )
    return resolved_dir, lpm_params.load_params(MODEL_NAME, resolved_dir)


def _load_shape_spec(spec: dict[str, Any]) -> ShapeFreeSpec:
    shapefree_cfg = spec.get("shapefree")
    if not isinstance(shapefree_cfg, dict):
        raise ValueError(f"{MODEL_NAME}: params.yaml is missing a 'shapefree' section")

    mode = str(shapefree_cfg.get("mode", "bounded")).strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(
            f"{MODEL_NAME}: unsupported shapefree.mode={mode!r}, expected one of {sorted(VALID_MODES)}"
        )

    edges = _validated_edges(shapefree_cfg)
    if mode == "bounded":
        return ShapeFreeSpec(mode=mode, edges=edges)
    return ShapeFreeSpec(
        mode=mode,
        edges=edges,
        support_end_max=_validated_support_end(shapefree_cfg, edges[-1]),
    )


def _validated_edges(config: dict[str, Any]) -> np.ndarray:
    edges = _as_float_array(list(config.get("edges", [])), field_name="shapefree.edges")
    if edges.size < 2:
        raise ValueError(
            f"{MODEL_NAME}: shapefree.edges must define at least two edges"
        )
    if not np.isfinite(edges).all():
        raise ValueError(f"{MODEL_NAME}: shapefree.edges must be finite")
    if not np.all(np.diff(edges) > 0.0):
        raise ValueError(f"{MODEL_NAME}: shapefree.edges must be strictly increasing")
    if not np.isclose(edges[0], 0.0):
        raise ValueError(f"{MODEL_NAME}: shapefree.edges must start at 0.0")

    return edges


def _validated_support_end(config: dict[str, Any], old_bin_start: float) -> float:
    support_end_max = config.get("support_end_max")
    if support_end_max is None:
        raise ValueError(
            f"{MODEL_NAME}: support_open mode requires shapefree.support_end_max"
        )
    try:
        support_end_max = float(support_end_max)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{MODEL_NAME}: invalid shapefree.support_end_max={support_end_max!r}"
        ) from exc
    if not np.isfinite(support_end_max):
        raise ValueError(f"{MODEL_NAME}: shapefree.support_end_max must be finite")
    if support_end_max <= old_bin_start:
        raise ValueError(
            f"{MODEL_NAME}: shapefree.support_end_max ({support_end_max}) "
            f"must be greater than the open old-bin start ({old_bin_start})"
        )
    return support_end_max


def _parameter_defaults(
    spec: dict[str, Any], n_fraction_bins: int
) -> tuple[dict[str, float], dict[str, str]]:
    parameter_defs = spec.get("parameters")
    if not isinstance(parameter_defs, list) or not parameter_defs:
        raise ValueError(
            f"{MODEL_NAME}: params.yaml must define at least one parameter"
        )

    expected_count = n_fraction_bins - 1
    if len(parameter_defs) != expected_count:
        raise ValueError(
            f"{MODEL_NAME}: expected {expected_count} latent parameters for {n_fraction_bins} bins, "
            f"got {len(parameter_defs)}"
        )

    values: dict[str, float] = {}
    units: dict[str, str] = {}
    for index, param in enumerate(parameter_defs, start=1):
        if not isinstance(param, dict):
            raise ValueError(f"{MODEL_NAME}: parameter #{index} must be a mapping")
        name = str(param.get("name", "")).strip()
        if not name:
            raise ValueError(f"{MODEL_NAME}: parameter #{index} is missing a name")
        values[name] = float(param.get("init", 0.0))
        units[name] = str(param.get("unit", "-"))
    return values, units


@register_lpm(MODEL_NAME)
class ShapeFreeNOldBinLpm(LpmBase):
    """Shape-free piecewise-uniform distribution with configurable old-bin support."""

    def __init__(self, directory_lpm=None):
        resolved_dir, spec = _load_model_spec(directory_lpm)
        self._shape = _load_shape_spec(spec)
        parameter_values, parameter_units = _parameter_defaults(
            spec, self._shape.n_bins
        )
        super().__init__(
            MODEL_NAME, parameter_values, parameter_units, str(resolved_dir)
        )

    def bin_edges(self) -> np.ndarray:
        """Return the finite bin edges used for the current shape specification."""
        return self._shape.effective_edges()

    def bin_widths(self) -> np.ndarray:
        """Return the effective bin widths."""
        return np.diff(self.bin_edges())

    def fractions(self) -> np.ndarray:
        """Return physical bin fractions reconstructed from latent parameters."""
        latent = np.asarray(self.get_parameters_to_array(), dtype=float)
        if latent.size == 0:
            return np.array([1.0], dtype=float)

        fractions = np.zeros(latent.size + 1, dtype=float)
        remaining = 1.0
        for idx, value in enumerate(expit(latent)):
            fractions[idx] = remaining * float(value)
            remaining -= fractions[idx]
        fractions[-1] = max(0.0, remaining)

        total = float(fractions.sum())
        if total <= 0.0:
            raise ValueError(
                f"{MODEL_NAME}: invalid fraction state with non-positive total mass"
            )
        return fractions / total

    def _pdf_array(self, t_arr: np.ndarray, edges: np.ndarray) -> np.ndarray:
        result = np.zeros_like(t_arr, dtype=float)
        widths = np.diff(edges)
        fractions = self.fractions()
        n_bins = len(widths)
        for idx, (left, right, width, fraction) in enumerate(
            zip(edges[:-1], edges[1:], widths, fractions, strict=False)
        ):
            if fraction <= 0.0 or width <= 0.0:
                continue
            if idx == n_bins - 1:
                mask = (t_arr >= left) & (t_arr <= right)
            else:
                mask = (t_arr >= left) & (t_arr < right)
            result[mask] = fraction / width
        return result

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Piecewise-uniform PDF over the default finite support."""
        t_arr = np.asarray(t, dtype=float)
        result = self._pdf_array(t_arr, self.bin_edges())
        return float(result) if np.isscalar(t) else result

    def _cdf_scalar(self, value: float, edges: np.ndarray) -> float:
        if value <= edges[0]:
            return 0.0
        if value >= edges[-1]:
            return 1.0

        fractions = self.fractions()
        cumulative_before = 0.0
        widths = np.diff(edges)
        for left, right, width, fraction in zip(
            edges[:-1], edges[1:], widths, fractions, strict=False
        ):
            if width <= 0.0:
                continue
            if value < right:
                local = (value - left) / width
                return float(np.clip(cumulative_before + fraction * local, 0.0, 1.0))
            cumulative_before += fraction
        return 1.0

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Piecewise-linear CDF over the configured bins."""
        t_arr = np.asarray(t, dtype=float)
        edges = self.bin_edges()
        if t_arr.ndim == 0:
            return self._cdf_scalar(float(t_arr), edges)
        return np.asarray(
            [self._cdf_scalar(float(value), edges) for value in t_arr], dtype=float
        )

    def cdf_and_partial_first_moment(
        self,
        t: npt.ArrayLike,
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        """Return exact cumulative mass and moment of the piecewise-uniform law."""
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        first_moment = np.zeros_like(values, dtype=float)
        edges = self.bin_edges()
        for left, right, width, fraction in zip(
            edges[:-1],
            edges[1:],
            np.diff(edges),
            self.fractions(),
            strict=False,
        ):
            if fraction <= 0.0 or width <= 0.0:
                continue
            upper = np.clip(values, left, right)
            first_moment += np.where(
                values > left,
                fraction * (upper - left) * (upper + left) / (2.0 * width),
                0.0,
            )
        if values.ndim == 0:
            return float(cdf), float(first_moment)
        return cdf, first_moment

    def _cdf_inv_scalar(self, probability: float, edges: np.ndarray) -> float:
        p = float(np.clip(probability, 0.0, 1.0))
        if p <= 0.0:
            return float(edges[0])
        if p >= 1.0:
            return float(edges[-1])

        fractions = self.fractions()
        widths = np.diff(edges)
        cumulative_before = 0.0
        for idx, (width, fraction) in enumerate(zip(widths, fractions, strict=False)):
            cumulative_after = cumulative_before + fraction
            if width <= 0.0:
                cumulative_before = cumulative_after
                continue
            if fraction > 0.0 and p <= cumulative_after + 1e-15:
                local = np.clip((p - cumulative_before) / fraction, 0.0, 1.0)
                return float(edges[idx] + local * width)
            cumulative_before = cumulative_after
        return float(edges[-1])

    def cdf_inv(self, p: float | npt.ArrayLike) -> float | npt.ArrayLike:
        """Inverse CDF computed analytically on each bin."""
        p_arr = np.asarray(p, dtype=float)
        edges = self.bin_edges()
        if p_arr.ndim == 0:
            return self._cdf_inv_scalar(float(p_arr), edges)
        return np.asarray(
            [self._cdf_inv_scalar(float(value), edges) for value in p_arr], dtype=float
        )

    def mean(self) -> float:
        """Return the mean age of the piecewise-uniform distribution."""
        edges = self.bin_edges()
        midpoints = 0.5 * (edges[:-1] + edges[1:])
        return float(np.dot(self.fractions(), midpoints))

    def std(self) -> float:
        """Return the standard deviation of the piecewise-uniform distribution."""
        edges = self.bin_edges()
        fractions = self.fractions()
        second_moment = np.sum(
            fractions
            * ((edges[:-1] ** 2 + edges[:-1] * edges[1:] + edges[1:] ** 2) / 3.0)
        )
        variance = max(0.0, float(second_moment - self.mean() ** 2))
        return float(np.sqrt(variance))
