# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Concentration-unit contracts evaluated only at API boundaries."""

from __future__ import annotations

from collections.abc import Iterable

_CANONICAL_UNITS = (
    "pptv",
    "TU",
    "pmC",
    "fraction_modern",
    "mol/l",
    "mol",
    "Bq/L",
    "dpm/ccKr",
    "TU_equivalent",
)
_CANONICAL_BY_CASEFOLD = {unit.casefold(): unit for unit in _CANONICAL_UNITS}
_NON_CANONICAL_UNIT_SUGGESTIONS = {
    "pcm%": "pmC",
    "%modern": "pmC",
}
_PLACEHOLDERS = {"0", "-", "n/a", "na", "none", "null", "unknown"}


def validate_unit_label(value: object, *, context: str) -> str:
    """Return a stripped unit label or reject ambiguous metadata.

    Known units must use their canonical spelling. Unknown labels remain
    available for custom tracers, but compatibility is always exact: this
    function never converts values and never treats different labels as equal.
    """
    if not isinstance(value, str):
        raise ValueError(f"{context} must be an explicit text value")
    unit = value.strip()
    if not unit or unit.casefold() in _PLACEHOLDERS:
        raise ValueError(f"{context} must be an explicit, non-placeholder unit")

    canonical = _NON_CANONICAL_UNIT_SUGGESTIONS.get(unit.casefold())
    if canonical is None:
        canonical = _CANONICAL_BY_CASEFOLD.get(unit.casefold())
    if canonical is not None and unit != canonical:
        raise ValueError(
            f"{context} uses non-canonical unit {unit!r}; use {canonical!r}"
        )
    return unit


def normalize_observation_units(
    elements: Iterable[object],
    units: Iterable[object],
) -> tuple[list[str], dict[str, str]]:
    """Validate row units and return normalized labels and tracer mapping."""
    normalized = []
    by_tracer: dict[str, str] = {}
    for row, (element, raw_unit) in enumerate(zip(elements, units, strict=True)):
        tracer = str(element)
        unit = validate_unit_label(
            raw_unit,
            context=f"Concentration unit at row {row}",
        )
        previous = by_tracer.get(tracer)
        if previous is not None and previous != unit:
            raise ValueError(
                f"Tracer {tracer!r} uses inconsistent observation units: "
                f"{previous!r} and {unit!r} (row {row})"
            )
        by_tracer[tracer] = unit
        normalized.append(unit)
    return normalized, by_tracer


__all__ = ["normalize_observation_units", "validate_unit_label"]
