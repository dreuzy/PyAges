# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes the validated observation containers and temporal summaries
# used by calibration and reporting code.
# It defines the public import boundary for concentration data, so callers can
# use stable names without depending on the internal storage modules.

"""Validated concentration observations used by PyAges workflows."""

from pyages.concentrations._container import Concentrations
from pyages.concentrations.schema import (
    CONCENTRATION_COLUMN,
    DATE_COLUMN,
    ELEMENT_COLUMN,
    ERROR_COLUMN,
    REFERENCE_COLUMNS,
    UNIT_COLUMN,
)
from pyages.concentrations.series import ConcentrationChronicle

__all__ = [
    "CONCENTRATION_COLUMN",
    "ConcentrationChronicle",
    "Concentrations",
    "DATE_COLUMN",
    "ELEMENT_COLUMN",
    "ERROR_COLUMN",
    "REFERENCE_COLUMNS",
    "UNIT_COLUMN",
]
