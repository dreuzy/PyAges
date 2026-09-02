# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines parameter distributions used before observations are fitted.

"""Load and evaluate the parameter priors used by MH calibration.

The prior describes which parameter values are plausible before the observed
concentrations are fitted. Parametric priors are read from the selected model's
validated ``params.yaml``. Empirical priors are built from one histogram per
parameter, extended to the model's calibration range, and normalized.

The :class:`Prior` class can initialize parameters, test whether a value is
allowed, and calculate either a density or a log-density. The sampler uses the
log-density to avoid numerical underflow and to keep impossible values at
exactly zero probability.

This module treats parameters as independent. It does not implement correlated
or hierarchical priors.
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
from scipy.stats import truncnorm

from pyages.calibration.methods.mh._prior_empirical import (
    EMPIRICAL_GRID_POINTS,
    EMPIRICAL_RELATIVE_TAIL_DECAY,
    build_empirical_prior_grid,
    histogram_moments,
)
from pyages.calibration.methods.mh._prior_parametric import (
    bounded_parametric_moments,
    effective_parametric_support,
    normal_pdf,
)
from pyages.calibration.methods.mh._prior_support import (
    open_unit_probability,
    validated_bounds,
)
from pyages.data_io.lpm_distribution import read_histogram


class Prior:
    """Prior distribution used by the Bayesian calibration.

    The prior can be parametric or defined empirically by a histogram. In both
    cases, one independent density is associated with every native LPM
    parameter. The LPM calibration range remains a separate operational
    constraint enforced by the sampler before the prior is evaluated.

    Parameters
    ----------
    option : bool
        Whether the prior contributes to the posterior.
    typ : str
        ``"parametric"`` or ``"empirical"``.
    prior_file : str
        Path prefix for empirical prior files.

    Notes
    -----
    :meth:`bounded_quantile`, :meth:`bounded_mode`, and :meth:`contains` form
    the marginal interface used by multi-chain initialization. The historical
    :meth:`param_init` method remains the one-chain compatibility path.

    """

    def __init__(
        self,
        option: bool = True,
        typ: str = "parametric",
        prior_file: str = "",
    ) -> None:
        """Initialize prior selection and empty per-parameter definitions."""
        if type(option) is not bool:
            raise TypeError("option must be a boolean")
        if typ not in {"parametric", "empirical"}:
            raise ValueError(f"Unsupported prior type: {typ}")
        if not isinstance(prior_file, str):
            raise TypeError("prior_file must be a string")
        self.option = option
        self.typ = typ
        self.prior_file = prior_file
        self.distributions: dict[str, str] = {}
        self.parameters: dict[str, Any] = {}
        self.source_sha256: dict[str, str] = {}

    def require_marginals(self, names: Sequence[str]) -> None:
        """Require an enabled, loaded marginal for every parameter in ``names``.

        This is the stable boundary used by ensemble initialization.  Callers
        do not need to inspect how parametric and empirical priors are stored.
        """
        if not self.option:
            raise ValueError("prior initialization requires an enabled prior")
        if self.typ == "parametric":
            missing = [
                name
                for name in names
                if name not in self.distributions or name not in self.parameters
            ]
        elif self.typ == "empirical":
            missing = [name for name in names if name not in self.parameters]
        else:  # defensive; the constructor validates ``typ``
            raise ValueError("prior must be parametric or empirical")
        if missing:
            raise ValueError(f"prior must be loaded for parameters {missing}")

    def _parametric_marginal(self, name: str) -> tuple[str, float, float]:
        """Return one validated parametric marginal definition."""
        self.require_marginals((name,))
        distribution = self.distributions[name]
        try:
            first, second = (float(item) for item in self.parameters[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Parametric prior is invalid for {name}") from exc
        if distribution == "normal":
            if not math.isfinite(first) or not math.isfinite(second) or second <= 0.0:
                raise ValueError(f"Normal prior parameters are invalid for {name}")
        elif distribution == "uniform":
            if not math.isfinite(first) or not math.isfinite(second) or second <= first:
                raise ValueError(f"Uniform prior bounds are invalid for {name}")
        else:
            raise ValueError(f"Unsupported prior distribution: {distribution}")
        return distribution, first, second

    def _empirical_marginal(self, name: str) -> tuple[np.ndarray, np.ndarray]:
        """Return one validated empirical density grid."""
        self.require_marginals((name,))
        try:
            histogram = np.asarray(self.parameters[name], dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Empirical prior is invalid for {name}") from exc
        if histogram.ndim != 2 or histogram.shape[1] != 2 or histogram.shape[0] < 2:
            raise ValueError(f"Empirical prior is invalid for {name}")
        values, density = histogram.T
        if (
            not np.all(np.isfinite(values))
            or not np.all(np.isfinite(density))
            or np.any(np.diff(values) <= 0.0)
            or np.any(density < 0.0)
        ):
            raise ValueError(f"Empirical prior is invalid for {name}")
        return values, density

    def _bounded_empirical_marginal(
        self,
        name: str,
        minimum: float,
        maximum: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Clip an empirical grid precisely to a finite calibration range."""
        values, density = self._empirical_marginal(name)
        support_minimum = max(minimum, float(values[0]))
        support_maximum = min(maximum, float(values[-1]))
        if support_maximum <= support_minimum:
            raise ValueError(f"Empirical prior has no positive support for {name}")
        interior = (values > support_minimum) & (values < support_maximum)
        clipped_values = np.concatenate(
            ([support_minimum], values[interior], [support_maximum])
        )
        clipped_density = np.interp(clipped_values, values, density)
        return clipped_values, clipped_density

    def bounded_quantile(
        self,
        name: str,
        minimum: float,
        maximum: float,
        probability: float,
    ) -> float:
        """Invert one marginal conditional on a finite calibration range.

        Parametric normal marginals use the exact truncated-normal inverse CDF;
        uniform marginals use their intersection with the operational interval.
        Empirical marginals integrate and invert the piecewise-linear density,
        including partial cells introduced by the calibration limits.
        """
        minimum, maximum = validated_bounds(minimum, maximum)
        probability = open_unit_probability(probability)
        if self.typ == "parametric":
            distribution, first, second = self._parametric_marginal(name)
            if distribution == "normal":
                value = float(
                    truncnorm.ppf(
                        probability,
                        (minimum - first) / second,
                        (maximum - first) / second,
                        loc=first,
                        scale=second,
                    )
                )
                if not math.isfinite(value):
                    raise ValueError(
                        f"Normal prior has no numerically usable mass for {name}"
                    )
                return float(np.clip(value, minimum, maximum))

            effective_minimum = max(minimum, first)
            effective_maximum = min(maximum, second)
            if effective_maximum <= effective_minimum:
                raise ValueError(f"Uniform prior has no positive support for {name}")
            return effective_minimum + probability * (
                effective_maximum - effective_minimum
            )

        if self.typ == "empirical":
            values, density = self._bounded_empirical_marginal(name, minimum, maximum)
            widths = np.diff(values)
            increments = 0.5 * (density[:-1] + density[1:]) * widths
            total = float(np.sum(increments))
            if not math.isfinite(total) or total <= 0.0:
                raise ValueError(f"Empirical prior has no positive mass for {name}")
            target = probability * total
            cumulative = np.concatenate(([0.0], np.cumsum(increments)))
            cell = min(
                int(np.searchsorted(cumulative, target, side="right") - 1),
                len(widths) - 1,
            )
            remaining = target - cumulative[cell]
            left_density = density[cell]
            slope = (density[cell + 1] - left_density) / widths[cell]
            if abs(slope) <= np.finfo(float).eps:
                offset = remaining / left_density if left_density > 0.0 else 0.0
            else:
                # Within a cell, integrating rho(x)=rho_0+s*x gives
                # remaining=rho_0*x+s*x^2/2. The displayed root is the one
                # continuous with remaining/rho_0 as the slope tends to zero.
                discriminant = max(0.0, left_density**2 + 2.0 * slope * remaining)
                offset = (-left_density + math.sqrt(discriminant)) / slope
            return float(np.clip(values[cell] + offset, values[cell], values[cell + 1]))

        raise ValueError("prior must be parametric or empirical")

    def bounded_mode(self, name: str, minimum: float, maximum: float) -> float:
        """Return a deterministic mode restricted to the calibration range.

        Uniform marginals deliberately use the midpoint of their effective
        support so every chain receives the same historical compatibility
        state for ``prior_map`` initialization.
        """
        minimum, maximum = validated_bounds(minimum, maximum)
        if self.typ == "parametric":
            distribution, first, second = self._parametric_marginal(name)
            if distribution == "normal":
                return float(np.clip(first, minimum, maximum))
            effective_minimum = max(minimum, first)
            effective_maximum = min(maximum, second)
            if effective_maximum <= effective_minimum:
                raise ValueError(f"Uniform prior has no positive support for {name}")
            return 0.5 * (effective_minimum + effective_maximum)

        if self.typ == "empirical":
            values, density = self._bounded_empirical_marginal(name, minimum, maximum)
            if not np.any(density > 0.0):
                raise ValueError(f"Empirical prior has no positive mass for {name}")
            return float(values[np.argmax(density)])

        raise ValueError("prior must be parametric or empirical")

    def contains(self, name: str, value: float) -> bool:
        """Return whether ``value`` has finite positive marginal density."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False
        if self.typ == "parametric":
            distribution, first, second = self._parametric_marginal(name)
            if distribution == "normal":
                return True
            return first <= value <= second
        if self.typ == "empirical":
            values, density = self._empirical_marginal(name)
            if value < values[0] or value > values[-1]:
                return False
            marginal_density = float(np.interp(value, values, density))
            return math.isfinite(marginal_density) and marginal_density > 0.0
        raise ValueError("prior must be parametric or empirical")

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
        when a normal prior assigns mass outside the calibration range.
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
            calibration_range = lpm.get_calibration_range(key)
            if self.typ == "parametric":
                value = self._param_init_parametric(
                    key, *calibration_range, rng, strategy
                )
            elif self.typ == "empirical":
                value = self._param_init_empirical(
                    key, *calibration_range, rng, strategy
                )
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
        if not self.prior_file:
            raise ValueError("prior_file must be non-empty for an empirical prior")
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
            # Scaling decay by the calibration-range width gives different physical
            # units the same relative boundary behavior.
            minimum, maximum = lpm.get_calibration_range(parameter)
            parameter_range = maximum - minimum
            if parameter_range <= 0.0:
                raise ValueError(
                    f"Empirical prior calibration range collapses for {parameter}"
                )
            decay = EMPIRICAL_RELATIVE_TAIL_DECAY / parameter_range
            x_values, probabilities = build_empirical_prior_grid(
                histogram[:, 0],
                histogram[:, 1],
                xmin=minimum,
                xmax=maximum,
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
                distribution, first, second = self._parametric_marginal(parameter)
                minimum, maximum = lpm.get_calibration_range(parameter)
                effective_support = effective_parametric_support(
                    distribution,
                    first,
                    second,
                    minimum,
                    maximum,
                )
                metadata[f"prior_effective_support_{parameter}"] = json.dumps(
                    effective_support
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
                histogram = self.parameters[parameter]
                metadata[f"prior_effective_support_{parameter}"] = json.dumps(
                    [float(histogram[0, 0]), float(histogram[-1, 0])]
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
                minimum, maximum = lpm.get_calibration_range(key)
                theory[key] = list(
                    bounded_parametric_moments(
                        self.distributions[key],
                        first,
                        second,
                        minimum,
                        maximum,
                    )
                )
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
