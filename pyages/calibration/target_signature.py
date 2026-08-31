# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Versioned identity of a prepared scientific calibration target.

The records in this module capture the effective LPM definition, ordered
observations, tracer inputs, and numerical convolution grids used by a
prepared calibration.  Reporting controls and source formatting are excluded,
so independently prepared but scientifically equivalent problems have the
same signature.

``CalibrationProblem`` owns preparation and objective evaluation.  This module
owns canonicalization, hashing, and the immutable value objects used to compare
those prepared targets before a multi-chain calculation starts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np

from pyages.data_io import lpm_params

if TYPE_CHECKING:
    from pyages.concentrations import Concentrations
    from pyages.convolution import ConvolutionTracers
    from pyages.lpm.core.lpm_base import LpmBase


CALIBRATION_TARGET_SIGNATURE_VERSION = 1


def _qualified_class_name(value: object) -> str:
    """Return a stable module-qualified class name for one scientific object."""
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _finite_float_hex(value: object, *, context: str) -> str:
    """Return one finite numeric value in an exact platform-stable form."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric") from exc
    if not np.isfinite(numeric):
        raise ValueError(f"{context} must be finite")
    return numeric.hex()


def _array_sha256(values: np.ndarray) -> tuple[int, str]:
    """Hash one finite vector after canonical little-endian float conversion."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise ValueError("prepared tracer-grid arrays must be finite vectors")
    canonical = np.ascontiguousarray(array, dtype="<f8")
    digest = hashlib.sha256()
    digest.update(str(canonical.size).encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical.tobytes(order="C"))
    return canonical.size, digest.hexdigest()


@dataclass(frozen=True)
class LpmParameterTargetSignature:
    """Resolved metadata for one ordered LPM parameter."""

    name: str
    unit: str
    lower_hex: str
    upper_hex: str
    initial_hex: str


@dataclass(frozen=True)
class LpmTargetSignature:
    """Resolved LPM identity and parameter contract used by a calibration."""

    class_name: str
    name: str
    convolution_strategy: str
    params_document_sha256: str
    fixed_state_sha256: str
    parameters: tuple[LpmParameterTargetSignature, ...]


@dataclass(frozen=True)
class ObservationTargetSignature:
    """One effective observation row in objective-function order."""

    element: str
    date_hex: str
    unit: str
    concentration_hex: str
    error_hex: str


@dataclass(frozen=True)
class TracerGridArraySignature:
    """Compact exact identity of one prepared tracer-grid vector."""

    size: int
    sha256: str


@dataclass(frozen=True)
class TracerGridTargetSignature:
    """Resolved tracer identity, numerical controls, and prepared grid."""

    tracer_class: str
    tracer_name: str
    tracer_unit: str
    tracer_datemin_hex: str
    tracer_datemax_hex: str
    tracer_signature_version: int
    tracer_scientific_sha256: str
    observation_date_hex: str
    grid_settings: tuple[tuple[str, str | int], ...]
    prepared_grid_date_hex: str | None
    edges: TracerGridArraySignature | None
    k_left: TracerGridArraySignature | None
    k_mid: TracerGridArraySignature | None
    k_right: TracerGridArraySignature | None


@dataclass(frozen=True)
class CalibrationTargetSignature:
    """Immutable, versioned identity of one prepared calibration target.

    Display paths and other reporting controls are deliberately absent. The
    signature contains only values that define the likelihood support or the
    forward calculation used by the prepared problem.
    """

    version: int
    lpm: LpmTargetSignature
    observations: tuple[ObservationTargetSignature, ...]
    tracer_grids: tuple[TracerGridTargetSignature, ...]

    @property
    def sha256(self) -> str:
        """Return a canonical digest suitable for persisted provenance."""
        serialized = json.dumps(
            asdict(self),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def differing_category(self, other: CalibrationTargetSignature) -> str | None:
        """Return the first top-level scientific category that differs."""
        if not isinstance(other, CalibrationTargetSignature):
            return "signature_type"
        if self.version != other.version:
            return "signature_version"
        if self.lpm != other.lpm:
            return "lpm"
        if self.observations != other.observations:
            return "observations"
        if self.tracer_grids != other.tracer_grids:
            return "tracer_grids"
        return None


def _canonical_scientific_value(value: object, *, context: str) -> object:
    """Normalize parsed scientific data without YAML formatting artifacts."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{context} mapping keys must be strings")
        return [
            "mapping",
            [
                [
                    key,
                    _canonical_scientific_value(
                        value[key],
                        context=f"{context}.{key}",
                    ),
                ]
                for key in sorted(value)
            ],
        ]
    if isinstance(value, (list, tuple)):
        return [
            "sequence",
            [
                _canonical_scientific_value(
                    item,
                    context=f"{context}[{index}]",
                )
                for index, item in enumerate(value)
            ],
        ]
    if value is None:
        return ["null"]
    if isinstance(value, (bool, np.bool_)):
        return ["boolean", bool(value)]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, (int, float, np.integer, np.floating)):
        return ["number", _finite_float_hex(value, context=context)]
    raise TypeError(f"{context} has unsupported value type {type(value).__name__}")


def _scientific_value_sha256(value: object, *, context: str) -> str:
    """Hash one canonical parsed scientific mapping or sequence."""
    normalized = _canonical_scientific_value(value, context=context)
    serialized = json.dumps(
        normalized,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _lpm_target_signature(lpm: LpmBase) -> LpmTargetSignature:
    """Capture ordered model metadata loaded by one prepared LPM."""
    names = tuple(lpm.get_param_names())
    units = lpm.parameter_units
    lower, upper = lpm.get_param_interval()
    initial = lpm.param_init()
    if not (
        len(names) == len(lower) == len(upper) == len(initial)
        and set(units) == set(names)
    ):
        raise ValueError("prepared LPM exposes inconsistent parameter metadata")
    parameters = tuple(
        LpmParameterTargetSignature(
            name=name,
            unit=str(units[name]),
            lower_hex=_finite_float_hex(minimum, context=f"lower bound for {name}"),
            upper_hex=_finite_float_hex(maximum, context=f"upper bound for {name}"),
            initial_hex=_finite_float_hex(start, context=f"initial value for {name}"),
        )
        for name, minimum, maximum, start in zip(
            names, lower, upper, initial, strict=True
        )
    )
    strategy = lpm.convolution_strategy
    strategy_name = getattr(strategy, "name", str(strategy))
    params_document = lpm_params.load_params(lpm.name, lpm.lpm_data_directory)
    fixed_state = lpm.fixed_scientific_state()
    return LpmTargetSignature(
        class_name=_qualified_class_name(lpm),
        name=str(lpm.name),
        convolution_strategy=str(strategy_name),
        params_document_sha256=_scientific_value_sha256(
            params_document,
            context=f"params.yaml for {lpm.name}",
        ),
        fixed_state_sha256=_scientific_value_sha256(
            fixed_state,
            context=f"fixed scientific state for {lpm.name}",
        ),
        parameters=parameters,
    )


def _observation_target_signatures(
    observations: Concentrations,
) -> tuple[ObservationTargetSignature, ...]:
    """Capture the exact effective observation rows in objective order."""
    frame = observations.frame
    required = ("element", "date", "unit", "concentration", "error")
    missing = [name for name in required if name not in frame]
    if missing:
        raise ValueError(f"prepared observations are missing columns {missing}")
    return tuple(
        ObservationTargetSignature(
            element=str(row.element),
            date_hex=_finite_float_hex(row.date, context="observation date"),
            unit=str(row.unit),
            concentration_hex=_finite_float_hex(
                row.concentration, context="observation concentration"
            ),
            error_hex=_finite_float_hex(row.error, context="observation error"),
        )
        for row in frame.loc[:, list(required)].itertuples(index=False)
    )


def _grid_settings_signature(settings: object) -> tuple[tuple[str, str | int], ...]:
    """Return immutable exact scalar controls for one convolution grid."""
    try:
        values = asdict(settings)
    except TypeError as exc:
        raise TypeError("convolution grid settings must be a dataclass") from exc
    signature: list[tuple[str, str | int]] = []
    for name, value in values.items():
        if isinstance(value, bool):
            raise ValueError(f"convolution setting {name!r} must not be boolean")
        if isinstance(value, int):
            signature.append((name, value))
        else:
            signature.append(
                (
                    name,
                    _finite_float_hex(value, context=f"convolution setting {name}"),
                )
            )
    return tuple(signature)


def _grid_array_signature(values: np.ndarray) -> TracerGridArraySignature:
    """Return one immutable vector size and digest pair."""
    size, digest = _array_sha256(values)
    return TracerGridArraySignature(size=size, sha256=digest)


def _tracer_grid_target_signatures(
    tracers: ConvolutionTracers,
) -> tuple[TracerGridTargetSignature, ...]:
    """Capture every tracer and prepared numerical grid in execution order."""
    signatures: list[TracerGridTargetSignature] = []
    for convolution in tracers.convolutions:
        tracer = convolution.tracer
        scientific_signature = tracer.scientific_signature()
        grid = convolution.prepared_grid
        if grid is None:
            grid_date = None
            edges = k_left = k_mid = k_right = None
        else:
            grid_date = _finite_float_hex(grid.date, context="prepared grid date")
            edges = _grid_array_signature(grid.edges)
            k_left = _grid_array_signature(grid.k_left)
            k_mid = _grid_array_signature(grid.k_mid)
            k_right = _grid_array_signature(grid.k_right)
        signatures.append(
            TracerGridTargetSignature(
                tracer_class=_qualified_class_name(tracer),
                tracer_name=str(tracer.name),
                tracer_unit=str(tracer.unit),
                tracer_datemin_hex=_finite_float_hex(
                    tracer.datemin, context=f"minimum date for tracer {tracer.name}"
                ),
                tracer_datemax_hex=_finite_float_hex(
                    tracer.datemax, context=f"maximum date for tracer {tracer.name}"
                ),
                tracer_signature_version=scientific_signature.version,
                tracer_scientific_sha256=scientific_signature.sha256,
                observation_date_hex=_finite_float_hex(
                    convolution.date,
                    context=f"observation date for tracer {tracer.name}",
                ),
                grid_settings=_grid_settings_signature(convolution.grid_settings),
                prepared_grid_date_hex=grid_date,
                edges=edges,
                k_left=k_left,
                k_mid=k_mid,
                k_right=k_right,
            )
        )
    return tuple(signatures)


def build_calibration_target_signature(
    lpm: LpmBase,
    observations: Concentrations,
    tracers: ConvolutionTracers,
) -> CalibrationTargetSignature:
    """Build the versioned identity of one fully prepared calibration target.

    Parameters
    ----------
    lpm
        Resolved LPM, including ordered parameter metadata and fixed scientific
        state.
    observations
        Effective observations after unit validation and uncertainty
        resolution.
    tracers
        Ordered, prepared tracer convolutions used by the objective.

    """
    return CalibrationTargetSignature(
        version=CALIBRATION_TARGET_SIGNATURE_VERSION,
        lpm=_lpm_target_signature(lpm),
        observations=_observation_target_signatures(observations),
        tracer_grids=_tracer_grid_target_signatures(tracers),
    )


__all__ = [
    "CALIBRATION_TARGET_SIGNATURE_VERSION",
    "CalibrationTargetSignature",
    "LpmParameterTargetSignature",
    "LpmTargetSignature",
    "ObservationTargetSignature",
    "TracerGridArraySignature",
    "TracerGridTargetSignature",
    "build_calibration_target_signature",
]
