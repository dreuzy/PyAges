# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file loads and validates the YAML definition of one tracer.

"""Convert tracer YAML metadata into a typed runtime configuration.

The loader resolves recharge-history settings, production, radioactive decay,
units, and valid dates into ``TracerConfig``. Unknown scalar fields, invalid
numeric values, and conflicting decay declarations are rejected before the
tracer opens its chronicle or participates in a convolution.

Configuration errors are kept distinct from missing or unreadable source data,
allowing callers to explain whether the YAML choices or the underlying files
need correction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from pyages._unit_contract import validate_unit_label
from pyages.tracer.decay import rate_from_config
from pyages.tracer.errors import TracerConfigError, TracerDataError

_CORE_KEYS = {
    "recharge_constant",
    "recharge",
    "production_rate",
    "half_life",
    "decay_mean_lifetime",
    "unit",
    "datemin",
    "datemax",
}


@dataclass(frozen=True)
class TracerConfig:
    """Normalized configuration needed by :class:`pyages.tracer.Tracer`."""

    unit: str
    recharge_constant: float | None = None
    has_chronicle: bool = False
    production_rate: float | None = None
    decay_rate: float | None = None
    datemin: float | None = None
    datemax: float | None = None

    @classmethod
    def from_mapping(cls, name: str, values: Mapping[str, Any]) -> "TracerConfig":
        """Validate and normalize one decoded YAML mapping."""
        for key, value in values.items():
            if key not in _CORE_KEYS and not isinstance(value, (dict, list)):
                raise TracerConfigError(f"Unknown parameter in {name}.yaml: '{key}'")

        try:
            decay_rate = rate_from_config(dict(values))
        except (TypeError, ValueError) as exc:
            raise TracerConfigError(f"Tracer {name}: {exc}") from exc

        production_rate = _optional_float(values, "production_rate", name)
        if production_rate is not None and production_rate < 0:
            raise TracerConfigError(
                f"Tracer {name}: Geoproduction rate must be non-negative, "
                f"got {production_rate}"
            )

        try:
            unit = validate_unit_label(
                values.get("unit"),
                context=f"Tracer {name} unit",
            )
        except ValueError as exc:
            raise TracerConfigError(str(exc)) from exc

        return cls(
            unit=unit,
            recharge_constant=_optional_float(values, "recharge_constant", name),
            has_chronicle=bool(values.get("recharge", False)),
            production_rate=production_rate,
            decay_rate=decay_rate,
            datemin=_optional_float(values, "datemin", name),
            datemax=_optional_float(values, "datemax", name),
        )


def _optional_float(
    values: Mapping[str, Any], key: str, tracer_name: str
) -> float | None:
    if key not in values or values[key] is None:
        return None
    try:
        return float(values[key])
    except (TypeError, ValueError) as exc:
        raise TracerConfigError(
            f"Tracer {tracer_name}: {key} must be numeric, got {values[key]!r}"
        ) from exc


def load_tracer_config(path: str | Path, name: str) -> TracerConfig:
    """Read and validate a tracer YAML file."""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as stream:
            values = yaml.safe_load(stream)
    except FileNotFoundError as exc:
        raise TracerDataError(
            f"YAML configuration file not found: {config_path}\n"
            f"Please create a .yaml configuration file for tracer '{name}'"
        ) from exc
    except yaml.YAMLError as exc:
        raise TracerDataError(
            f"Error parsing YAML configuration {config_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise TracerDataError(
            f"Error reading YAML configuration {config_path}: {exc}"
        ) from exc

    if not isinstance(values, dict):
        raise TracerConfigError(
            f"YAML configuration must be a dictionary, got {type(values).__name__}"
        )
    return TracerConfig.from_mapping(name, values)
