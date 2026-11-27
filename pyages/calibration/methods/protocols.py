# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Structural typing contracts for independent calibration algorithms."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pyages.calibration.problem import CalibrationProblem
    from pyages.lpm.samples.table import LpmSampleTable


class CalibrationAlgorithm(Protocol):
    """Operations required by calibration orchestration and output services."""

    method: str
    runtime_seconds: float

    @property
    def problem(self) -> CalibrationProblem:
        """Return the problem bound during ``run``."""
        ...

    def run(self, problem: CalibrationProblem) -> LpmSampleTable:
        """Execute the algorithm against a prepared problem."""
        ...

    def write_parameters(self, file_name: str | Path) -> None:
        """Write the effective algorithm configuration."""
        ...

    def write_results(self, file_name: str | Path) -> None:
        """Write scalar run diagnostics."""
        ...


__all__ = ["CalibrationAlgorithm"]
