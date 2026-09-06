# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes ``CalibrationProblem`` as the explicit public entry point
# for preparing a fit, making the supported package API visible to tooling.

"""Small public API for calibration."""

from __future__ import annotations

from pyages.calibration.problem import CalibrationProblem

__all__ = ["CalibrationProblem"]
