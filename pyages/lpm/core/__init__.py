# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes parameter management through the core LPM package.
# Concrete models use the exported helper to load YAML starting values and
# ranges, then convert ordered calibration vectors back to named parameters.

"""Core LPM interfaces and helpers."""

from pyages.lpm.core.parameter_manager import ParameterManager

__all__ = ["ParameterManager"]
