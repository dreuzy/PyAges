# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Independent parameter priors used by Metropolis--Hastings calibration.

Parametric priors are read from the selected LPM's validated ``params.yaml``.
Empirical priors are reconstructed from one histogram per parameter, extended
to the physical LPM bounds, and normalized. The :class:`Prior` object exposes
both density and log-density evaluation; the sampler uses log densities to
preserve exact zero support and avoid floating-point underflow.

Priors factorize over native LPM parameters. Correlated or hierarchical priors
are not represented by this module.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from pyages.data_io.lpm_distribution import read_histogram

EMPIRICAL_GRID_POINTS = 101
EMPIRICAL_RELATIVE_TAIL_DECAY = 500.0


def _validated_empirical_inputs(
    x_data: Sequence[float],
    y_data: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return validated one-dimensional empirical support and density."""
    values = np.asarray(x_data, dtype=float)
    density = np.asarray(y_data, dtype=float)
    if values.ndim != 1 or density.ndim != 1 or values.shape != density.shape:
        raise ValueError(
            "x_data and y_data must be one-dimensional arrays of equal size"
        )
    if values.size < 2:
        raise ValueError("An empirical prior requires at least two grid points")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(density)):
        raise ValueError("Empirical prior values and densities must be finite")
    if np.any(np.diff(values) <= 0.0):
        raise ValueError("Empirical prior values must be strictly increasing")
    if np.any(density < 0.0):
        raise ValueError("Empirical prior densities must be non-negative")
    return values, density


def _validate_empirical_grid_controls(
    xmin: float,
    xmax: float,
    n_points: int,
    decay_left: float,
    decay_right: float,
) -> None:
    """Validate interpolation bounds, resolution, and tail decay."""
    if not math.isfinite(xmin) or not math.isfinite(xmax) or xmax <= xmin:
        raise ValueError("Empirical prior bounds must be finite and increasing")
    if isinstance(n_points, bool) or not isinstance(n_points, int) or n_points < 2:
        raise ValueError("n_points must be an integer greater than one")
    if (
        not math.isfinite(decay_left)
        or not math.isfinite(decay_right)
        or decay_left < 0.0
        or decay_right < 0.0
    ):
        raise ValueError("Empirical prior decay rates must be finite and non-negative")


def build_empirical_prior_grid(
    x_data: Sequence[float],
    y_data: Sequence[float],
    xmin: float = 0.0,
    xmax: float = 70.0,
    n_points: int = 2000,
    decay_left: float = 10.0,
    decay_right: float = 10.0,
    normalize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate histogram points and extend them with exponential tails.

    The samples define a piecewise-linear density on their original support.
    Exponential tails connect the edge densities to the requested LPM bounds.
    When ``normalize`` is true, trapezoidal mass over the returned grid is one.
    This construction applies to empirical parameter priors, not LPM transit
    time distributions.
    """
    x_data, y_data = _validated_empirical_inputs(x_data, y_data)
    _validate_empirical_grid_controls(
        xmin,
        xmax,
        n_points,
        decay_left,
        decay_right,
    )
    # Values between supplied histogram centers follow a linear density model.
    interpolate = interp1d(
        x_data,
        y_data,
        kind="linear",
        bounds_error=False,
        fill_value=0,
    )

    x_cont = np.linspace(xmin, xmax, n_points)
    y_cont = interpolate(x_cont)
    # Tails avoid a discontinuous jump at the empirical grid edge while the
    # configured physical bounds still provide finite support.
    left_mask = x_cont < x_data.min()
    right_mask = x_cont > x_data.max()
    if y_data[0] > 0:
        y_cont[left_mask] = y_data[0] * np.exp(
            -decay_left * (x_data[0] - x_cont[left_mask])
        )
    if y_data[-1] > 0:
        y_cont[right_mask] = y_data[-1] * np.exp(
            -decay_right * (x_cont[right_mask] - x_data[-1])
        )

    if normalize:
        # Tail mass belongs to the prior and is included in normalization.
        area = np.trapezoid(y_cont, x_cont)
        if not math.isfinite(area) or area <= 0.0:
            raise ValueError("Empirical prior must have positive finite mass")
        y_cont /= area
    return x_cont, y_cont


def normal_pdf(x: float, x0: float, sigma: float) -> float:
    r"""Evaluate :math:`\mathcal{N}(x\mid x_0,\sigma^2)` at one point."""
    if not math.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("Normal prior std must be finite and positive")
    numerator = math.exp(-((x - x0) ** 2) / (2.0 * sigma**2))
    denominator = math.sqrt(2 * math.pi * sigma**2)
    return numerator / denominator


def histogram_moments(histogram: np.ndarray) -> tuple[float, float]:
    """Integrate the mean and variance of a two-column density grid.

    Column zero contains parameter values and column one contains density. The
    density need not already be normalized; its finite positive mass is divided
    out before moments are returned.
    """
    density = histogram[:, 1]
    values = histogram[:, 0]
    total = float(np.trapezoid(density, values))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("Histogram density must have positive finite mass")
    mean = float(np.trapezoid(values * density, values) / total)
    second = float(np.trapezoid(values**2 * density, values) / total)
    variance = max(0.0, second - mean**2)
    return mean, variance


class Prior:
    """Prior distribution used by the Bayesian calibration.

    The prior can be parametric or defined empirically by a histogram. In both
    cases, one independent density is associated with every native LPM
    parameter. LPM bounds remain a separate hard support enforced by the
    sampler before the prior is evaluated.

    Parameters
    ----------
    option : bool
        Whether the prior contributes to the posterior.
    typ : str
        ``"parametric"`` or ``"empirical"``.
    prior_file : str
        Path prefix for empirical prior files.
    """

    def __init__(
        self,
        option: bool = True,
        typ: str = "parametric",
        prior_file: str = "",
    ) -> None:
        """Initialize prior selection and empty per-parameter definitions."""
        if typ not in {"parametric", "empirical"}:
            raise ValueError(f"Unsupported prior type: {typ}")
        self.option = option
        self.typ = typ
        self.prior_file = prior_file
        self.distributions: dict[str, str] = {}
        self.parameters: dict[str, Any] = {}
        self.source_sha256: dict[str, str] = {}

    def _param_init_parametric(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Return one bounded parametric-prior initial value.

        ``map`` selects the normal mean or uniform midpoint; ``sample`` draws
        from the configured density. Clipping guarantees a valid LPM state
        when a normal prior assigns mass outside the model bounds.
        """
        distribution = self.distributions[key]
        first, second = self.parameters[key]
        if distribution == "normal":
            value = first if strategy == "map" else rng.normal(first, second)
            return float(np.clip(value, pmin, pmax))
        if distribution == "uniform":
            value = (
                0.5 * (first + second)
                if strategy == "map"
                else rng.uniform(first, second)
            )
            return float(np.clip(value, pmin, pmax))
        raise ValueError(f"Unsupported prior distribution: {distribution}")

    def _param_init_empirical(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Return one bounded initialization from an empirical density grid.

        Sampling integrates trapezoidal cell masses into a CDF rather than
        treating grid points as an equally spaced categorical distribution.
        """
        values, probabilities = self.parameters[key].T
        if np.all((probabilities <= 0) | ~np.isfinite(probabilities)):
            return 0.5 * (pmin + pmax)
        if strategy == "map":
            value = float(values[np.argmax(probabilities)])
        else:
            increments = (
                0.5 * (probabilities[:-1] + probabilities[1:]) * np.diff(values)
            )
            cdf = np.concatenate([[0.0], np.cumsum(increments)])
            if cdf[-1] > 0:
                cdf /= cdf[-1]
                value = float(np.interp(rng.random(), cdf, values))
            else:
                value = float(values[np.argmax(probabilities)])
        return float(np.clip(value, pmin, pmax))

    def param_init(
        self,
        lpm: Any,
        strategy: str = "map",
        rng: np.random.Generator | None = None,
    ) -> None:
        """Initialize model parameters from the configured prior.

        Parameter order follows ``lpm.p`` and the model is updated only after
        every value has been selected.
        """
        if strategy not in {"map", "sample"}:
            raise ValueError("strategy must be 'map' or 'sample'")
        if rng is None:
            rng = np.random.default_rng()
        parameters = []
        for key in lpm.p:
            bounds = lpm.get_p_min(key), lpm.get_p_max(key)
            if self.typ == "parametric":
                value = self._param_init_parametric(key, *bounds, rng, strategy)
            elif self.typ == "empirical":
                value = self._param_init_empirical(key, *bounds, rng, strategy)
            parameters.append(value)
        lpm.set_param_from_array(parameters)

    def _load_parametric_priors(self, lpm: Any) -> None:
        """Load validated independent priors in native LPM parameter order."""
        from pyages.data_io import lpm_params

        self.distributions = {}
        self.parameters = {}
        self.source_sha256 = {}
        schema = lpm_params.load_parameter_schema(
            lpm.name,
            lpm.lpm_data_directory,
        )
        for name, prior in lpm_params.get_priors(schema).items():
            prior_type = prior.get("type")
            if not prior_type:
                continue
            self.distributions[name] = prior_type
            if prior_type == "uniform":
                self.parameters[name] = [prior.get("min"), prior.get("max")]
            elif prior_type == "normal":
                self.parameters[name] = [prior.get("mean"), prior.get("std")]
        expected = list(lpm.p)
        missing = [name for name in expected if name not in self.distributions]
        extra = [name for name in self.distributions if name not in lpm.p]
        if missing or extra:
            raise ValueError(
                "Configured parametric priors must match the LPM parameters "
                f"(missing={missing}, extra={extra})"
            )

    def _load_empirical_priors(self, lpm: Any) -> None:
        """Load and extend one empirical density grid per LPM parameter."""
        self.parameters = {}
        self.source_sha256 = {}
        for parameter in lpm.get_param_names():
            source = Path(f"{self.prior_file}_{parameter}.txt")
            source_bytes = source.read_bytes()
            histogram = read_histogram(
                f"{self.prior_file}.txt",
                parameter,
            ).to_numpy()
            if source.read_bytes() != source_bytes:
                raise RuntimeError(
                    f"Empirical prior source changed while loading {parameter!r}"
                )
            self.source_sha256[parameter] = hashlib.sha256(source_bytes).hexdigest()
            # Scaling decay by the parameter range gives different physical
            # units the same relative boundary behavior.
            parameter_range = abs(lpm.get_p_min(parameter) - lpm.get_p_max(parameter))
            if parameter_range <= 0.0:
                raise ValueError(f"Empirical prior bounds collapse for {parameter}")
            decay = EMPIRICAL_RELATIVE_TAIL_DECAY / parameter_range
            x_values, probabilities = build_empirical_prior_grid(
                histogram[:, 0],
                histogram[:, 1],
                xmin=lpm.get_p_min(parameter),
                xmax=lpm.get_p_max(parameter),
                n_points=EMPIRICAL_GRID_POINTS,
                decay_left=decay,
                decay_right=decay,
            )
            self.parameters[parameter] = np.column_stack((x_values, probabilities))

    def load(self, lpm: Any) -> None:
        """Load prior definitions for a model."""
        if not self.option:
            return
        if self.typ == "parametric":
            self._load_parametric_priors(lpm)
        elif self.typ == "empirical":
            self._load_empirical_priors(lpm)

    def resolved_metadata(self, lpm: Any) -> dict[str, str | int]:
        """Return scalar metadata for the prior definitions currently loaded."""
        metadata: dict[str, str | int] = {}
        if not self.option:
            return metadata
        for parameter in lpm.get_param_names():
            if self.typ == "parametric":
                metadata[f"prior_distribution_{parameter}"] = self.distributions[
                    parameter
                ]
                metadata[f"prior_parameters_{parameter}"] = json.dumps(
                    self.parameters[parameter],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            else:
                metadata[f"prior_distribution_{parameter}"] = "empirical"
                if parameter in self.source_sha256:
                    metadata[f"prior_sha256_{parameter}"] = self.source_sha256[
                        parameter
                    ]
                    metadata[f"prior_grid_points_{parameter}"] = len(
                        self.parameters[parameter]
                    )
        return metadata

    def _evaluate_parametric(self, lpm: Any, params: list[float]) -> float:
        """Multiply independent parametric densities in probability space."""
        probability = 1.0
        for index, key in enumerate(lpm.p):
            distribution = self.distributions[key]
            first, second = self.parameters[key]
            if distribution == "normal":
                probability *= normal_pdf(params[index], first, second)
            elif distribution == "uniform":
                if first <= params[index] <= second:
                    probability /= abs(second - first)
                else:
                    probability = 0
            else:
                raise ValueError(f"Unsupported prior distribution: {distribution}")
        return probability

    def _evaluate_empirical(self, lpm: Any, params: list[float]) -> float:
        """Multiply linearly interpolated empirical densities."""
        probability = 1.0
        for index, parameter in enumerate(lpm.get_param_names()):
            histogram = self.parameters[parameter]
            if params[index] < histogram[0, 0] or params[index] > histogram[-1, 0]:
                return 0.0
            density = float(np.interp(params[index], histogram[:, 0], histogram[:, 1]))
            if density <= 0.0 or not math.isfinite(density):
                return 0.0
            probability *= density
        return probability

    def evaluate(self, lpm: Any, params: list[float]) -> float:
        """Evaluate the factorized prior density for the current parameters.

        This probability-space form remains available for diagnostics. MCMC
        acceptance uses :meth:`log_evaluate` for numerical stability.
        """
        if self.typ == "parametric":
            probability = self._evaluate_parametric(lpm, params)
        elif self.typ == "empirical":
            probability = self._evaluate_empirical(lpm, params)
        return probability

    def _log_evaluate_parametric(self, lpm: Any, params: list[float]) -> float:
        """Sum parametric log densities with exact support checks."""
        log_probability = 0.0
        for index, key in enumerate(lpm.p):
            distribution = self.distributions[key]
            first, second = self.parameters[key]
            value = params[index]
            if distribution == "normal":
                if second <= 0.0:
                    raise ValueError(f"Normal prior std must be positive for {key}")
                standardized = (value - first) / second
                log_probability += (
                    -0.5 * standardized**2
                    - math.log(second)
                    - 0.5 * math.log(2.0 * math.pi)
                )
            elif distribution == "uniform":
                if second <= first:
                    raise ValueError(f"Uniform prior bounds are invalid for {key}")
                if not first <= value <= second:
                    return -math.inf
                log_probability -= math.log(second - first)
            else:
                raise ValueError(f"Unsupported prior distribution: {distribution}")
        return log_probability

    def _log_evaluate_empirical(self, lpm: Any, params: list[float]) -> float:
        """Sum empirical log densities with exact zero support."""
        log_probability = 0.0
        for index, parameter in enumerate(lpm.get_param_names()):
            histogram = self.parameters[parameter]
            value = params[index]
            if value < histogram[0, 0] or value > histogram[-1, 0]:
                return -math.inf
            density = float(np.interp(value, histogram[:, 0], histogram[:, 1]))
            if density <= 0.0 or not math.isfinite(density):
                return -math.inf
            log_probability += math.log(density)
        return log_probability

    def log_evaluate(self, lpm: Any, params: list[float]) -> float:
        """Evaluate the prior log-density with exact zero support."""
        if self.typ == "parametric":
            return self._log_evaluate_parametric(lpm, params)
        if self.typ == "empirical":
            return self._log_evaluate_empirical(lpm, params)
        raise AssertionError("validated prior type was not handled")

    def validate_chain_moments(
        self,
        path: pd.DataFrame,
        lpm: Any,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Compare sampled prior moments with theoretical expectations.

        This diagnostic is intended for likelihood-free sampler qualification.
        It is not a convergence diagnostic for observational chains.
        """
        sampled = {
            key: [
                np.nanmean(path[key].to_numpy(), dtype="float"),
                np.nanvar(path[key].to_numpy(), dtype="float"),
            ]
            for key in lpm.p
        }
        theory = copy.deepcopy(sampled)
        if self.typ == "parametric":
            for key in lpm.p:
                first, second = self.parameters[key]
                if self.distributions[key] == "normal":
                    theory[key] = [first, second**2]
                elif self.distributions[key] == "uniform":
                    theory[key] = [
                        (first + second) / 2,
                        ((second - first) / np.sqrt(12)) ** 2,
                    ]
        elif self.typ == "empirical":
            for key in lpm.p:
                theory[key] = list(histogram_moments(self.parameters[key]))

        differences = copy.deepcopy(sampled)
        for key in lpm.p:
            for index in (0, 1):
                reference = theory[key][index]
                differences[key][index] = (
                    math.nan
                    if reference == 0.0
                    else 100.0 * (sampled[key][index] - reference) / abs(reference)
                )
        return {
            "sampled": {
                key: {"mean": value[0], "var": value[1]}
                for key, value in sampled.items()
            },
            "theory": {
                key: {"mean": value[0], "var": value[1]}
                for key, value in theory.items()
            },
            "difference_percent": {
                key: {"mean": value[0], "var": value[1]}
                for key, value in differences.items()
            },
        }


__all__ = [
    "Prior",
    "build_empirical_prior_grid",
    "histogram_moments",
    "normal_pdf",
]
