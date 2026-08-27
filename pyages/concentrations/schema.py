# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical concentration-table columns and key formatting."""

from math import isfinite

ELEMENT_COLUMN = "element"
CONCENTRATION_COLUMN = "concentration"
ERROR_COLUMN = "error"
UNIT_COLUMN = "unit"
DATE_COLUMN = "date"

REFERENCE_COLUMNS = (
    ELEMENT_COLUMN,
    CONCENTRATION_COLUMN,
    ERROR_COLUMN,
    UNIT_COLUMN,
    DATE_COLUMN,
)


def tracer_date_key(element: str, date: float) -> str:
    """Return the canonical key used to align tracer/date model columns."""
    normalized_element = str(element).strip()
    normalized_date = float(date)
    if not normalized_element:
        raise ValueError("element must be a non-empty string")
    if not isfinite(normalized_date):
        raise ValueError("date must be finite")
    return f"{normalized_element}@{normalized_date!r}"


__all__ = [
    "CONCENTRATION_COLUMN",
    "DATE_COLUMN",
    "ELEMENT_COLUMN",
    "ERROR_COLUMN",
    "REFERENCE_COLUMNS",
    "UNIT_COLUMN",
    "tracer_date_key",
]
