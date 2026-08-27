# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Common interface for calibration algorithms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pyages.calibration.outputs import (
    display_calibrated_models,
    write_calibrated_result,
    write_key_values,
)
from pyages.calibration.problem import CalibrationProblem


class CalibrationMethod(ABC):
    """A calibration algorithm bound explicitly to a prepared problem."""

    method: str

    def __init__(self) -> None:
        """Initialize an unbound calibration method and its timing state."""
        self._problem: CalibrationProblem | None = None
        self.time_perform = 0.0

    @property
    def problem(self) -> CalibrationProblem:
        """Return the bound prepared problem, or fail before :meth:`run`."""
        if self._problem is None:
            raise RuntimeError("Call run(problem) before using calibration results.")
        return self._problem

    @property
    def observations(self):
        """Return observations from the bound calibration problem."""
        return self.problem.observations

    @property
    def lpm(self):
        """Return the prepared LPM from the bound calibration problem."""
        self.problem.ensure_prepared()
        return self.problem.lpm

    @property
    def tracers(self):
        """Return prepared tracers from the bound calibration problem."""
        self.problem.ensure_prepared()
        return self.problem.tracers

    @property
    def display_options(self):
        """Return display options from the bound calibration problem."""
        return self.problem.display_options

    def _bind_problem(self, problem: CalibrationProblem) -> None:
        problem.ensure_prepared()
        self._problem = problem

    def run(self, problem: CalibrationProblem):
        """Bind a prepared problem and execute the algorithm."""
        self._bind_problem(problem)
        return self.perform()

    def objective_function(
        self,
        parameters,
        observed_values,
        observed_errors,
        conc: bool = False,
    ):
        """Delegate objective evaluation to the prepared problem."""
        return self.problem.objective_function(
            parameters,
            observed_values,
            observed_errors,
            return_concentrations=conc,
        )

    def analysis_calibration(self, results=None) -> None:
        """Run the problem's optional systematic analysis."""
        self.problem.analyze(results)

    def display_lpms(self, display_options, results, lpm_reference=None) -> None:
        """Display calibrated models without embedding plotting in the method."""
        display_calibrated_models(
            self,
            self.problem,
            results,
            display_options,
            reference=lpm_reference,
        )

    def write_calibrated_lpm(
        self,
        results,
        file_prior: str | None = None,
        folder_prior: str = "",
    ) -> None:
        """Write the standard files for the completed run."""
        write_calibrated_result(
            self,
            self.problem,
            results,
            prior_file=file_prior,
            prior_folder=folder_prior,
        )

    def write_results(self, file_name: str | Path) -> None:
        """Write execution time and method-specific scalar results."""
        values: dict[str, Any] = {"time_perform": self.time_perform}
        self.write_results_spec(values)
        write_key_values(file_name, values)

    @abstractmethod
    def perform(self):
        """Execute the method after :meth:`run` binds a problem."""

    @abstractmethod
    def write_parameters(self, file_name: str | Path) -> None:
        """Write method configuration."""

    @abstractmethod
    def write_results_spec(self, data: dict[str, Any]) -> None:
        """Add method-specific result values."""


__all__ = ["CalibrationMethod"]
