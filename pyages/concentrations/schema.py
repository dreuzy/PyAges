# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical concentration-table column names."""

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

__all__ = [
    "CONCENTRATION_COLUMN",
    "DATE_COLUMN",
    "ELEMENT_COLUMN",
    "ERROR_COLUMN",
    "REFERENCE_COLUMNS",
    "UNIT_COLUMN",
]
