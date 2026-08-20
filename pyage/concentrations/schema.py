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
