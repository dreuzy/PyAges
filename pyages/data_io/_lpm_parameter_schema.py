# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines and validates the immutable schema of one LPM parameter file.

"""Validate mathematical domains, calibration ranges, starts, steps, and priors.

The functions in this private module are pure with respect to the filesystem.
The public :mod:`pyages.data_io.lpm_params` facade owns file loading and cache
lifetime while re-exporting the schema records defined here.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


class LPMParamsError(ValueError):
    """Raised when LPM parameters are missing or malformed."""


@dataclass(frozen=True, slots=True)
class LPMParameterDomain:
    """Mathematical validity domain independent of calibration and prior choices."""

    minimum: float | None
    maximum: float | None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True

    def contains(self, value: float) -> bool:
        """Return whether one finite value belongs to this domain."""
        if not math.isfinite(value):
            return False
        if self.minimum is not None:
            if value < self.minimum or (
                value == self.minimum and not self.minimum_inclusive
            ):
                return False
        if self.maximum is not None:
            if value > self.maximum or (
                value == self.maximum and not self.maximum_inclusive
            ):
                return False
        return True


@dataclass(frozen=True, slots=True)
class LPMParameterDefinition:
    """Validated runtime metadata for one LPM parameter."""

    name: str
    domain: LPMParameterDomain
    calibration_range: tuple[float, float]
    init: float
    step: float | None
    prior: Mapping[str, Any] | None

    @property
    def bounds(self) -> tuple[float, float]:
        """Return the legacy alias for :attr:`calibration_range`."""
        return self.calibration_range

    def __deepcopy__(self, memo: dict[int, Any]) -> LPMParameterDefinition:
        """Reuse this immutable value in deep-copied LPM instances."""
        del memo
        return self


@dataclass(frozen=True, slots=True)
class LPMParameterSchema:
    """Immutable runtime schema parsed from one LPM parameter file."""

    model: str
    parameters: tuple[LPMParameterDefinition, ...]
    version: int = 1

    def __deepcopy__(self, memo: dict[int, Any]) -> LPMParameterSchema:
        """Reuse this immutable value in deep-copied LPM instances."""
        del memo
        return self

    @property
    def names(self) -> tuple[str, ...]:
        """Return parameter names in YAML declaration order."""
        return tuple(parameter.name for parameter in self.parameters)


def _freeze(value: Any) -> Any:
    """Recursively convert YAML containers to read-only equivalents."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return copy.deepcopy(value)


def _thaw(value: Any) -> Any:
    """Return ordinary mutable containers for a frozen YAML value."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return copy.deepcopy(value)


def _finite_float(value: object, *, message: str) -> float:
    """Convert one value to a finite float or raise a schema error."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise LPMParamsError(message) from exc
    if not math.isfinite(numeric_value):
        raise LPMParamsError(message)
    return numeric_value


def _optional_finite_float(value: object, *, message: str) -> float | None:
    """Return ``None`` for an unbounded side or one finite float."""
    if value is None:
        return None
    return _finite_float(value, message=message)


def _validated_domain(
    raw_domain: object,
    *,
    model_name: str,
    parameter_name: str,
    legacy_range: tuple[float, float],
) -> LPMParameterDomain:
    """Validate an explicit mathematical domain or derive the legacy fallback."""
    if raw_domain is None:
        return LPMParameterDomain(legacy_range[0], legacy_range[1])
    if not isinstance(raw_domain, Mapping):
        raise LPMParamsError(
            f"{model_name}: domain for parameter {parameter_name!r} must be a mapping"
        )
    minimum = _optional_finite_float(
        raw_domain.get("min"),
        message=f"{model_name}: invalid domain minimum for {parameter_name!r}",
    )
    maximum = _optional_finite_float(
        raw_domain.get("max"),
        message=f"{model_name}: invalid domain maximum for {parameter_name!r}",
    )
    minimum_inclusive = raw_domain.get("min_inclusive", True)
    maximum_inclusive = raw_domain.get("max_inclusive", True)
    if type(minimum_inclusive) is not bool or type(maximum_inclusive) is not bool:
        raise LPMParamsError(
            f"{model_name}: domain inclusivity for parameter {parameter_name!r} "
            "must be boolean"
        )
    if minimum is not None and maximum is not None:
        if minimum > maximum or (
            minimum == maximum and not (minimum_inclusive and maximum_inclusive)
        ):
            raise LPMParamsError(
                f"{model_name}: invalid mathematical domain for {parameter_name!r}"
            )
    return LPMParameterDomain(
        minimum,
        maximum,
        minimum_inclusive,
        maximum_inclusive,
    )


def _validated_prior(
    raw_prior: Mapping[str, Any],
    *,
    model_name: str,
    parameter_name: str,
) -> dict[str, Any]:
    """Normalize one supported prior without applying a calibration range.

    Uniform priors require finite, strictly increasing ``min`` and ``max``
    values. Normal priors require a finite ``mean`` and a finite, strictly
    positive ``std``. The returned copy retains any additional metadata while
    replacing these numerical fields with floats.

    Compatibility with the parameter's calibration range is intentionally
    checked later by :func:`_parameter_definition`, once both specifications are
    available. Unsupported or incomplete prior types raise ``LPMParamsError``.
    """
    prior_type = raw_prior.get("type")
    if not isinstance(prior_type, str) or not prior_type:
        raise LPMParamsError(
            f"{model_name}: prior for parameter {parameter_name!r} must define a type"
        )
    if prior_type not in {"uniform", "normal"}:
        raise LPMParamsError(
            f"{model_name}: unsupported prior type {prior_type!r} "
            f"for parameter {parameter_name!r}"
        )

    prior = dict(raw_prior)
    if prior_type == "uniform":
        if "min" not in raw_prior or "max" not in raw_prior:
            raise LPMParamsError(
                f"{model_name}: uniform prior for parameter {parameter_name!r} "
                "requires 'min' and 'max'"
            )
        minimum = _finite_float(
            raw_prior["min"],
            message=(
                f"{model_name}: uniform prior bounds for parameter "
                f"{parameter_name!r} must be finite"
            ),
        )
        maximum = _finite_float(
            raw_prior["max"],
            message=(
                f"{model_name}: uniform prior bounds for parameter "
                f"{parameter_name!r} must be finite"
            ),
        )
        if minimum >= maximum:
            raise LPMParamsError(
                f"{model_name}: uniform prior minimum must be lower than maximum "
                f"for parameter {parameter_name!r}"
            )
        prior["min"] = minimum
        prior["max"] = maximum
        return prior

    if "mean" not in raw_prior or "std" not in raw_prior:
        raise LPMParamsError(
            f"{model_name}: {prior_type} prior for parameter {parameter_name!r} "
            "requires 'mean' and 'std'"
        )
    mean = _finite_float(
        raw_prior["mean"],
        message=(
            f"{model_name}: {prior_type} prior mean for parameter "
            f"{parameter_name!r} must be finite"
        ),
    )
    standard_deviation = _finite_float(
        raw_prior["std"],
        message=(
            f"{model_name}: {prior_type} prior standard deviation for parameter "
            f"{parameter_name!r} must be finite and strictly positive"
        ),
    )
    if standard_deviation <= 0.0:
        raise LPMParamsError(
            f"{model_name}: {prior_type} prior standard deviation for parameter "
            f"{parameter_name!r} must be finite and strictly positive"
        )
    prior["mean"] = mean
    prior["std"] = standard_deviation
    return prior


def _validated_calibration_range(
    raw_parameter: Mapping[str, Any],
    *,
    model_name: str,
    parameter_name: str,
) -> tuple[float, float]:
    """Return the canonical range while accepting the legacy ``bounds`` key."""
    legacy = raw_parameter.get("bounds")
    canonical = raw_parameter.get("calibration_range")
    if legacy is not None and canonical is not None:
        if not isinstance(legacy, (list, tuple)) or not isinstance(
            canonical, (list, tuple)
        ):
            raise LPMParamsError(
                f"{model_name}: parameter {parameter_name!r} must define two bounds"
            )
        if legacy != canonical:
            raise LPMParamsError(
                f"{model_name}: bounds and calibration_range disagree "
                f"for {parameter_name!r}"
            )
    raw_range = canonical if canonical is not None else legacy
    if not isinstance(raw_range, (list, tuple)) or len(raw_range) != 2:
        raise LPMParamsError(
            f"{model_name}: parameter {parameter_name!r} must define two bounds"
        )
    lower = _finite_float(
        raw_range[0],
        message=f"{model_name}: invalid bounds for parameter {parameter_name!r}",
    )
    upper = _finite_float(
        raw_range[1],
        message=f"{model_name}: invalid bounds for parameter {parameter_name!r}",
    )
    if lower > upper:
        raise LPMParamsError(
            f"{model_name}: lower bound exceeds upper bound for {parameter_name!r}"
        )
    return lower, upper


def _validated_step(
    raw_parameter: Mapping[str, Any],
    *,
    model_name: str,
    parameter_name: str,
) -> float | None:
    """Return an optional strictly-positive proposal step."""
    if "step" not in raw_parameter:
        return None
    step = _finite_float(
        raw_parameter["step"],
        message=f"{model_name}: invalid proposal step for parameter {parameter_name!r}",
    )
    if step <= 0.0:
        raise LPMParamsError(
            f"{model_name}: proposal step for parameter {parameter_name!r} "
            "must be strictly positive"
        )
    return step


def _validated_optional_prior(
    raw_parameter: Mapping[str, Any],
    *,
    model_name: str,
    parameter_name: str,
) -> Mapping[str, Any] | None:
    """Validate and freeze an optional prior definition."""
    raw_prior = raw_parameter.get("prior")
    if raw_prior is None:
        return None
    if not isinstance(raw_prior, Mapping):
        raise LPMParamsError(
            f"{model_name}: prior for parameter {parameter_name!r} must be a mapping"
        )
    return _freeze(
        _validated_prior(
            raw_prior,
            model_name=model_name,
            parameter_name=parameter_name,
        )
    )


def _parameter_definition(
    raw_parameter: object,
    *,
    model_name: str,
    index: int,
) -> LPMParameterDefinition:
    """Resolve all interacting constraints for one YAML parameter entry.

    The canonical calibration range may come from ``calibration_range`` or the
    legacy ``bounds`` spelling. An explicit mathematical domain may be wider or
    open-ended; when absent, the calibration range becomes the legacy domain.
    Both calibration endpoints must belong to that domain, and ``init`` must be
    finite and lie inside the calibration range.

    The optional proposal step and parametric prior are normalized separately.
    A uniform prior must retain positive-width support after intersection with
    the calibration range. The returned immutable definition is therefore safe
    for both model construction and calibration configuration.
    """
    if not isinstance(raw_parameter, Mapping):
        raise LPMParamsError(f"{model_name}: parameter #{index + 1} must be a mapping")

    name = raw_parameter.get("name")
    if not isinstance(name, str) or not name:
        raise LPMParamsError(f"{model_name}: parameter #{index + 1} has no valid name")

    # Resolve the nested intervals before values that depend on them: physical
    # domain contains calibration range, which in turn contains the start.
    lower, upper = _validated_calibration_range(
        raw_parameter,
        model_name=model_name,
        parameter_name=name,
    )

    domain = _validated_domain(
        raw_parameter.get("domain"),
        model_name=model_name,
        parameter_name=name,
        legacy_range=(lower, upper),
    )
    if not domain.contains(lower) or not domain.contains(upper):
        raise LPMParamsError(
            f"{model_name}: calibration_range for parameter {name!r} "
            "must lie inside its mathematical domain"
        )

    if "init" not in raw_parameter:
        raise LPMParamsError(f"{model_name}: parameter {name!r} has no initial value")
    initial = _finite_float(
        raw_parameter["init"],
        message=(
            f"{model_name}: initial value for parameter {name!r} "
            f"must be finite and within [{lower}, {upper}]"
        ),
    )
    if not lower <= initial <= upper:
        raise LPMParamsError(
            f"{model_name}: initial value for parameter {name!r} "
            f"must be finite and within [{lower}, {upper}]"
        )

    # Proposal and prior fields are optional, but when present they participate
    # in the same parameter contract rather than remaining unchecked metadata.
    step = _validated_step(
        raw_parameter,
        model_name=model_name,
        parameter_name=name,
    )
    prior = _validated_optional_prior(
        raw_parameter,
        model_name=model_name,
        parameter_name=name,
    )
    if prior is not None and prior["type"] == "uniform":
        effective_lower = max(lower, float(prior["min"]))
        effective_upper = min(upper, float(prior["max"]))
        if effective_lower >= effective_upper:
            raise LPMParamsError(
                f"{model_name}: uniform prior for parameter {name!r} has no "
                "positive-width overlap with its calibration range"
            )

    return LPMParameterDefinition(
        name=name,
        domain=domain,
        calibration_range=(lower, upper),
        init=initial,
        step=step,
        prior=prior,
    )


def parse_parameter_schema(
    params: Mapping[str, Any],
    *,
    expected_model: str | None = None,
) -> LPMParameterSchema:
    """Validate a parsed parameter mapping and return its immutable schema.

    Parameters
    ----------
    params : mapping
        Parsed contents of a ``params.yaml`` document.
    expected_model : str, optional
        Model identifier implied by the file location or caller.

    Returns
    -------
    LPMParameterSchema
        Immutable version-1 schema with validated parameter metadata.

    Raises
    ------
    LPMParamsError
        If the document version, parameter declarations, proposal steps, or
        supported parametric priors are invalid.
    """
    model_name = params.get("model")
    if not isinstance(model_name, str) or not model_name:
        label = expected_model or "LPM"
        raise LPMParamsError(f"{label}: params.yaml has no valid model identifier")
    if expected_model is not None and model_name != expected_model:
        raise LPMParamsError(
            f"{expected_model}: params.yaml declares model {model_name!r}"
        )

    version = params.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise LPMParamsError(
            f"{model_name}: unsupported params.yaml version {version!r}; expected 1"
        )

    raw_parameters = params.get("parameters")
    if not isinstance(raw_parameters, list) or not raw_parameters:
        raise LPMParamsError(f"{model_name}: 'parameters' must be a non-empty list")

    definitions: list[LPMParameterDefinition] = []
    names: set[str] = set()
    for index, raw_parameter in enumerate(raw_parameters):
        definition = _parameter_definition(
            raw_parameter,
            model_name=model_name,
            index=index,
        )
        if definition.name in names:
            raise LPMParamsError(
                f"{model_name}: duplicate parameter name {definition.name!r}"
            )
        names.add(definition.name)
        definitions.append(definition)

    return LPMParameterSchema(
        model=model_name,
        parameters=tuple(definitions),
        version=version,
    )


__all__ = [
    "LPMParameterDefinition",
    "LPMParameterDomain",
    "LPMParameterSchema",
    "LPMParamsError",
    "parse_parameter_schema",
]
