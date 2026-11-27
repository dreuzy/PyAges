# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Composition helper binding one algorithm to one prepared problem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations.schema import CONCENTRATION_COLUMN, ERROR_COLUMN

if TYPE_CHECKING:
    from pyages.concentrations import Concentrations
    from pyages.config.runtime import DisplayOptions
    from pyages.lpm.core.lpm_base import LpmBase


@dataclass(slots=True)
class CalibrationBinding:
    """Hold the prepared scientific context used by one algorithm instance."""

    _problem: CalibrationProblem | None = None

    def bind(self, problem: CalibrationProblem) -> None:
        """Validate and retain a prepared problem."""
        problem.ensure_prepared()
        self._problem = problem

    @property
    def problem(self) -> CalibrationProblem:
        """Return the bound problem, failing clearly before ``run``."""
        if self._problem is None:
            raise RuntimeError("Call run(problem) before using calibration results.")
        return self._problem

    @property
    def observations(self) -> Concentrations:
        """Return observations in their canonical order."""
        return self.problem.observations

    @property
    def lpm(self) -> LpmBase:
        """Return the prepared LPM."""
        self.problem.ensure_prepared()
        lpm = self.problem.lpm
        if lpm is None:  # pragma: no cover - guarded by ensure_prepared().
            raise RuntimeError("Prepared calibration problem has no LPM.")
        return lpm

    @property
    def display_options(self) -> DisplayOptions:
        """Return output and rendering choices for the problem."""
        return self.problem.display_options

    def objective_function(
        self,
        parameters,
        observed_values,
        observed_errors,
        conc: bool = False,
    ):
        """Evaluate the prepared problem objective."""
        return self.problem.objective_function(
            parameters,
            observed_values,
            observed_errors,
            return_concentrations=conc,
        )

    def observation_arrays(
        self,
        observations: Concentrations | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return ordered observed concentrations and errors."""
        if observations is None:
            return self.problem.prepared_observation_arrays()
        values = observations.frame[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        errors = observations.frame[ERROR_COLUMN].to_numpy(dtype=float)
        return values, errors


__all__ = ["CalibrationBinding"]
