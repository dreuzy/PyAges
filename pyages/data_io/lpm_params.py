# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Load, validate, and content-cache LPM ``params.yaml`` files."""

from __future__ import annotations

import copy
import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml


class LPMParamsError(ValueError):
    """Raised when LPM parameters are missing or malformed."""


@dataclass(frozen=True, slots=True)
class LPMParameterDefinition:
    """Validated runtime metadata for one LPM parameter."""

    name: str
    bounds: tuple[float, float]
    init: float
    step: float | None
    prior: Mapping[str, Any] | None

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


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    """One parsed file and the exact byte content for which it is valid."""

    fingerprint: bytes
    document: dict[str, Any]
    schema: LPMParameterSchema


_PARAMS_CACHE: dict[Path, _CacheEntry] = {}
_PARAMS_CACHE_LOCK = threading.RLock()


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


def _params_path(model_name: str, data_dir: str | Path) -> Path:
    """Return a normalized absolute path for one parameter file."""
    return (Path(data_dir) / model_name / "params.yaml").resolve()


def _finite_float(value: object, *, message: str) -> float:
    """Convert one value to a finite float or raise a schema error."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise LPMParamsError(message) from exc
    if not math.isfinite(numeric_value):
        raise LPMParamsError(message)
    return numeric_value


def _validated_prior(
    raw_prior: Mapping[str, Any],
    *,
    model_name: str,
    parameter_name: str,
) -> dict[str, Any]:
    """Validate and normalize one supported parametric-prior mapping."""
    prior_type = raw_prior.get("type")
    if not isinstance(prior_type, str) or not prior_type:
        raise LPMParamsError(
            f"{model_name}: prior for parameter {parameter_name!r} must define a type"
        )
    if prior_type not in {"uniform", "normal", "gaussian"}:
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


def _parameter_definition(
    raw_parameter: object,
    *,
    model_name: str,
    index: int,
) -> LPMParameterDefinition:
    """Validate and freeze one entry from the YAML ``parameters`` list."""
    if not isinstance(raw_parameter, Mapping):
        raise LPMParamsError(f"{model_name}: parameter #{index + 1} must be a mapping")

    name = raw_parameter.get("name")
    if not isinstance(name, str) or not name:
        raise LPMParamsError(f"{model_name}: parameter #{index + 1} has no valid name")

    bounds = raw_parameter.get("bounds")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
        raise LPMParamsError(f"{model_name}: parameter {name!r} must define two bounds")
    lower = _finite_float(
        bounds[0],
        message=f"{model_name}: invalid bounds for parameter {name!r}",
    )
    upper = _finite_float(
        bounds[1],
        message=f"{model_name}: invalid bounds for parameter {name!r}",
    )
    if lower > upper:
        raise LPMParamsError(
            f"{model_name}: lower bound exceeds upper bound for {name!r}"
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

    step: float | None = None
    if "step" in raw_parameter:
        step = _finite_float(
            raw_parameter["step"],
            message=f"{model_name}: invalid proposal step for parameter {name!r}",
        )
        if step <= 0.0:
            raise LPMParamsError(
                f"{model_name}: proposal step for parameter {name!r} "
                "must be strictly positive"
            )

    raw_prior = raw_parameter.get("prior")
    if raw_prior is not None and not isinstance(raw_prior, Mapping):
        raise LPMParamsError(
            f"{model_name}: prior for parameter {name!r} must be a mapping"
        )
    prior = (
        None
        if raw_prior is None
        else _freeze(
            _validated_prior(
                raw_prior,
                model_name=model_name,
                parameter_name=name,
            )
        )
    )

    return LPMParameterDefinition(
        name=name,
        bounds=(lower, upper),
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


def _read_parameter_bytes(path: Path) -> bytes:
    """Read one parameter file and normalize filesystem errors."""
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise LPMParamsError(f"Missing params.yaml: {path}") from exc
    except OSError as exc:
        raise LPMParamsError(f"Cannot read params.yaml: {path}") from exc


def _read_cache_entry(model_name: str, data_dir: str | Path) -> _CacheEntry:
    """Return a cache entry matching the file's exact current content."""
    path = _params_path(model_name, data_dir)
    content = _read_parameter_bytes(path)
    with _PARAMS_CACHE_LOCK:
        cached = _PARAMS_CACHE.get(path)
        if cached is not None and cached.fingerprint == content:
            return cached

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LPMParamsError(f"params.yaml is not valid UTF-8: {path}") from exc
    try:
        document = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise LPMParamsError(f"Malformed params.yaml: {path}") from exc
    if not isinstance(document, dict):
        raise LPMParamsError(f"{model_name}: params.yaml root must be a mapping")
    schema = parse_parameter_schema(document, expected_model=model_name)

    entry = _CacheEntry(
        fingerprint=content,
        document=document,
        schema=schema,
    )
    with _PARAMS_CACHE_LOCK:
        current = _PARAMS_CACHE.get(path)
        if current is not None and current.fingerprint == content:
            return current
        _PARAMS_CACHE[path] = entry
    return entry


def clear_params_cache() -> None:
    """Discard all content-keyed parameter documents and validated schemas."""
    with _PARAMS_CACHE_LOCK:
        _PARAMS_CACHE.clear()


def load_params(model_name: str, data_dir: str | Path) -> dict[str, Any]:
    """Load a validated ``params.yaml`` document and return a defensive copy.

    Cache reuse requires byte-for-byte identical UTF-8 file content; file
    timestamps and sizes are not used as freshness indicators.
    """
    return copy.deepcopy(_read_cache_entry(model_name, data_dir).document)


def load_parameter_schema(
    model_name: str,
    data_dir: str | Path,
) -> LPMParameterSchema:
    """Load one validated, immutable LPM parameter schema."""
    return _read_cache_entry(model_name, data_dir).schema


def get_bounds(
    schema: LPMParameterSchema,
) -> dict[str, tuple[float, float]]:
    """Return ``{parameter_name: (minimum, maximum)}`` bounds."""
    return {parameter.name: parameter.bounds for parameter in schema.parameters}


def get_init(
    schema: LPMParameterSchema,
) -> dict[str, float]:
    """Return ``{parameter_name: initial_value}``."""
    return {parameter.name: parameter.init for parameter in schema.parameters}


def get_steps(
    schema: LPMParameterSchema,
) -> dict[str, float]:
    """Return configured proposal steps, omitting parameters without one."""
    return {
        parameter.name: parameter.step
        for parameter in schema.parameters
        if parameter.step is not None
    }


def get_priors(
    schema: LPMParameterSchema,
) -> dict[str, dict[str, Any]]:
    """Return defensive copies of configured prior mappings."""
    return {
        parameter.name: _thaw(parameter.prior)
        for parameter in schema.parameters
        if parameter.prior is not None
    }
