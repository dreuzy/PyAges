# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Independent scalar prior distributions used by MH calibration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np
from scipy.stats import truncnorm

from pyages.calibration.methods.mh._prior_empirical import histogram_moments
from pyages.calibration.methods.mh._prior_parametric import (
    bounded_parametric_moments,
    effective_parametric_support,
    normal_pdf,
)
from pyages.calibration.methods.mh._prior_support import (
    open_unit_probability,
    validated_bounds,
)


class PriorMarginal(Protocol):
    """Behavior required from one independent parameter prior."""

    def bounded_quantile(
        self, minimum: float, maximum: float, probability: float
    ) -> float:
        """Return a quantile restricted to the operational bounds."""
        ...

    def contains(self, value: float) -> bool:
        """Return whether the prior support contains a finite value."""
        ...

    def initial_value(
        self,
        minimum: float,
        maximum: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Draw or select one valid initialization value."""
        ...

    def density(self, value: float) -> float:
        """Evaluate the scalar probability density."""
        ...

    def log_density(self, value: float) -> float:
        """Evaluate the scalar log-density."""
        ...

    def moments(self, minimum: float, maximum: float) -> tuple[float, float]:
        """Return the mean and variance within operational bounds."""
        ...

    def metadata(self, minimum: float, maximum: float) -> dict[str, str | int]:
        """Describe the persisted distribution and its effective support."""
        ...


@dataclass(frozen=True, slots=True)
class NormalMarginal:
    """Normal density interpreted inside an operational calibration range."""

    name: str
    mean: float
    std: float

    def _validate(self) -> None:
        if not math.isfinite(self.mean) or not math.isfinite(self.std):
            raise ValueError(f"Normal prior parameters are invalid for {self.name}")
        if self.std <= 0.0:
            raise ValueError(f"Normal prior std must be positive for {self.name}")

    def bounded_quantile(
        self, minimum: float, maximum: float, probability: float
    ) -> float:
        """Return a truncated-normal quantile inside the supplied bounds."""
        self._validate()
        minimum, maximum = validated_bounds(minimum, maximum)
        probability = open_unit_probability(probability)
        value = float(
            truncnorm.ppf(
                probability,
                (minimum - self.mean) / self.std,
                (maximum - self.mean) / self.std,
                loc=self.mean,
                scale=self.std,
            )
        )
        if not math.isfinite(value):
            raise ValueError(
                f"Normal prior has no numerically usable mass for {self.name}"
            )
        return float(np.clip(value, minimum, maximum))

    def contains(self, value: float) -> bool:
        """Return whether *value* is finite and hence in normal support."""
        self._validate()
        return math.isfinite(value)

    def initial_value(
        self,
        minimum: float,
        maximum: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Select the mode or draw a normal initialization value."""
        self._validate()
        value = self.mean if strategy == "map" else rng.normal(self.mean, self.std)
        return float(np.clip(value, minimum, maximum))

    def density(self, value: float) -> float:
        """Evaluate the normal probability density at *value*."""
        self._validate()
        return normal_pdf(value, self.mean, self.std)

    def log_density(self, value: float) -> float:
        """Evaluate the normal log-density at *value*."""
        self._validate()
        standardized = (value - self.mean) / self.std
        return (
            -0.5 * standardized**2 - math.log(self.std) - 0.5 * math.log(2.0 * math.pi)
        )

    def moments(self, minimum: float, maximum: float) -> tuple[float, float]:
        """Return moments of the normal density inside the bounds."""
        self._validate()
        return bounded_parametric_moments(
            "normal", self.mean, self.std, minimum, maximum
        )

    def metadata(self, minimum: float, maximum: float) -> dict[str, str | int]:
        """Return serializable normal-prior metadata."""
        self._validate()
        return {
            "distribution": "normal",
            "parameters": json.dumps([self.mean, self.std]),
            "effective_support": json.dumps(
                effective_parametric_support(
                    "normal", self.mean, self.std, minimum, maximum
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class UniformMarginal:
    """Uniform density with finite inclusive support."""

    name: str
    minimum: float
    maximum: float

    def _validate(self) -> None:
        if (
            not math.isfinite(self.minimum)
            or not math.isfinite(self.maximum)
            or self.maximum <= self.minimum
        ):
            raise ValueError(f"Uniform prior bounds are invalid for {self.name}")

    def _effective_support(self, minimum: float, maximum: float) -> tuple[float, float]:
        self._validate()
        minimum, maximum = validated_bounds(minimum, maximum)
        lower = max(minimum, self.minimum)
        upper = min(maximum, self.maximum)
        if upper <= lower:
            raise ValueError(f"Uniform prior has no positive support for {self.name}")
        return lower, upper

    def bounded_quantile(
        self, minimum: float, maximum: float, probability: float
    ) -> float:
        """Return a quantile on the intersection of both support ranges."""
        probability = open_unit_probability(probability)
        lower, upper = self._effective_support(minimum, maximum)
        return lower + probability * (upper - lower)

    def contains(self, value: float) -> bool:
        """Return whether *value* belongs to the uniform support."""
        self._validate()
        return math.isfinite(value) and self.minimum <= value <= self.maximum

    def initial_value(
        self,
        minimum: float,
        maximum: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Select the midpoint or draw a uniform initialization value."""
        self._validate()
        value = (
            0.5 * (self.minimum + self.maximum)
            if strategy == "map"
            else rng.uniform(self.minimum, self.maximum)
        )
        return float(np.clip(value, minimum, maximum))

    def density(self, value: float) -> float:
        """Evaluate the uniform probability density at *value*."""
        self._validate()
        if not self.minimum <= value <= self.maximum:
            return 0.0
        return 1.0 / (self.maximum - self.minimum)

    def log_density(self, value: float) -> float:
        """Evaluate the uniform log-density at *value*."""
        density = self.density(value)
        return -math.inf if density == 0.0 else math.log(density)

    def moments(self, minimum: float, maximum: float) -> tuple[float, float]:
        """Return moments of the uniform density inside the bounds."""
        self._validate()
        return bounded_parametric_moments(
            "uniform", self.minimum, self.maximum, minimum, maximum
        )

    def metadata(self, minimum: float, maximum: float) -> dict[str, str | int]:
        """Return serializable uniform-prior metadata."""
        self._validate()
        return {
            "distribution": "uniform",
            "parameters": json.dumps([self.minimum, self.maximum]),
            "effective_support": json.dumps(
                effective_parametric_support(
                    "uniform", self.minimum, self.maximum, minimum, maximum
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class EmpiricalMarginal:
    """Piecewise-linear density represented by value-density grid rows."""

    name: str
    histogram: np.ndarray
    source_sha256: str | None = None

    def density_grid(self) -> np.ndarray:
        """Return a detached validated value-density grid."""
        values, density = self._arrays(strict=True)
        return np.column_stack((values, density))

    def _arrays(self, *, strict: bool) -> tuple[np.ndarray, np.ndarray]:
        try:
            histogram = np.asarray(self.histogram, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Empirical prior is invalid for {self.name}") from exc
        if histogram.ndim != 2 or histogram.shape[1] != 2 or histogram.shape[0] < 2:
            raise ValueError(f"Empirical prior is invalid for {self.name}")
        values, density = histogram.T
        if strict and (
            not np.all(np.isfinite(values))
            or not np.all(np.isfinite(density))
            or np.any(np.diff(values) <= 0.0)
            or np.any(density < 0.0)
        ):
            raise ValueError(f"Empirical prior is invalid for {self.name}")
        return values, density

    def _bounded_grid(
        self, minimum: float, maximum: float
    ) -> tuple[np.ndarray, np.ndarray]:
        minimum, maximum = validated_bounds(minimum, maximum)
        values, density = self._arrays(strict=True)
        lower = max(minimum, float(values[0]))
        upper = min(maximum, float(values[-1]))
        if upper <= lower:
            raise ValueError(f"Empirical prior has no positive support for {self.name}")
        interior = (values > lower) & (values < upper)
        clipped_values = np.concatenate(([lower], values[interior], [upper]))
        return clipped_values, np.interp(clipped_values, values, density)

    def bounded_quantile(
        self, minimum: float, maximum: float, probability: float
    ) -> float:
        """Invert the piecewise-linear CDF inside the supplied bounds."""
        probability = open_unit_probability(probability)
        values, density = self._bounded_grid(minimum, maximum)
        widths = np.diff(values)
        increments = 0.5 * (density[:-1] + density[1:]) * widths
        total = float(np.sum(increments))
        if not math.isfinite(total) or total <= 0.0:
            raise ValueError(f"Empirical prior has no positive mass for {self.name}")
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
            discriminant = max(0.0, left_density**2 + 2.0 * slope * remaining)
            offset = (-left_density + math.sqrt(discriminant)) / slope
        return float(np.clip(values[cell] + offset, values[cell], values[cell + 1]))

    def contains(self, value: float) -> bool:
        """Return whether *value* lies on positive empirical support."""
        values, density = self._arrays(strict=True)
        if not math.isfinite(value) or value < values[0] or value > values[-1]:
            return False
        marginal_density = float(np.interp(value, values, density))
        return math.isfinite(marginal_density) and marginal_density > 0.0

    def initial_value(
        self,
        minimum: float,
        maximum: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """Select the grid mode or sample the empirical CDF."""
        values, density = self._arrays(strict=False)
        if np.all((density <= 0) | ~np.isfinite(density)):
            return 0.5 * (minimum + maximum)
        if strategy == "map":
            value = float(values[np.argmax(density)])
        else:
            increments = 0.5 * (density[:-1] + density[1:]) * np.diff(values)
            cdf = np.concatenate([[0.0], np.cumsum(increments)])
            if cdf[-1] > 0:
                cdf /= cdf[-1]
                value = float(np.interp(rng.random(), cdf, values))
            else:
                value = float(values[np.argmax(density)])
        return float(np.clip(value, minimum, maximum))

    def density(self, value: float) -> float:
        """Interpolate the empirical density at *value*."""
        values, density = self._arrays(strict=False)
        if value < values[0] or value > values[-1]:
            return 0.0
        result = float(np.interp(value, values, density))
        return result if result > 0.0 and math.isfinite(result) else 0.0

    def log_density(self, value: float) -> float:
        """Evaluate the empirical log-density at *value*."""
        density = self.density(value)
        return -math.inf if density == 0.0 else math.log(density)

    def moments(self, minimum: float, maximum: float) -> tuple[float, float]:
        """Return moments of the stored empirical histogram."""
        del minimum, maximum
        return histogram_moments(np.asarray(self.histogram, dtype=float))

    def metadata(self, minimum: float, maximum: float) -> dict[str, str | int]:
        """Return serializable empirical-prior metadata."""
        del minimum, maximum
        values, _density = self._arrays(strict=False)
        metadata: dict[str, str | int] = {
            "distribution": "empirical",
            "effective_support": json.dumps([float(values[0]), float(values[-1])]),
        }
        if self.source_sha256 is not None:
            metadata["sha256"] = self.source_sha256
            metadata["grid_points"] = len(values)
        return metadata


def parametric_marginal(
    name: str,
    distribution: str,
    parameters: Sequence[object],
) -> PriorMarginal:
    """Build one named parametric marginal from validated scalar parameters."""
    try:
        first, second = (float(item) for item in parameters)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Parametric prior is invalid for {name}") from exc
    if distribution == "normal":
        return NormalMarginal(name, first, second)
    if distribution == "uniform":
        return UniformMarginal(name, first, second)
    raise ValueError(f"Unsupported prior distribution: {distribution}")


__all__ = [
    "EmpiricalMarginal",
    "NormalMarginal",
    "PriorMarginal",
    "UniformMarginal",
    "parametric_marginal",
]
