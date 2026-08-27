# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Nelder-Mead calibration methods."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.optimize import minimize

from pyages.calibration.methods.base import CalibrationMethod
from pyages.calibration.outputs import write_key_values
from pyages.calibration.utils.objective_functions import normalized_residual_norm
from pyages.lpm.samples.table import LpmSampleTable

if TYPE_CHECKING:
    from pyages.concentrations import Concentrations

SIMPLEX = "Simplex"
MULTI_START = "Simplex_multi_start"
FORWARD_UNCERTAINTY = "forward_uncertainty_quantification"
VALID_METHODS = {SIMPLEX, MULTI_START, FORWARD_UNCERTAINTY}


class Simplex(CalibrationMethod):
    """Calibrate an LPM with Nelder-Mead and optional repeated starts."""

    def __init__(
        self,
        calibration_method: str,
        *,
        init_multiples_n: int = 2,
        fuq_n: int = 10,
    ) -> None:
        """Configure one supported Simplex or forward-UQ execution mode."""
        super().__init__()
        if calibration_method not in VALID_METHODS:
            raise ValueError(
                f"Unknown simplex calibration method: {calibration_method}"
            )
        for name, value in (
            ("init_multiples_n", init_multiples_n),
            ("fuq_n", fuq_n),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.method = calibration_method
        self.x_tolerance = 1e-8
        self.function_tolerance = 1e-8
        self.initialization_count = init_multiples_n
        self.initialization_seed = 12345
        self.uncertainty_seed = 123456
        self.uncertainty_sample_count = fuq_n
        self._optimization_runs: list[dict[str, Any]] = []

    def perform(self) -> LpmSampleTable:
        """Execute the configured Simplex variant on the bound problem."""
        start = perf_counter()
        self._optimization_runs = []
        if self.method == SIMPLEX:
            results = self._run_single()
        elif self.method == MULTI_START:
            results = self._run_multiple()
        else:
            results = self._run_forward_uncertainty()
        self.time_perform = perf_counter() - start
        return results.add_moments()

    def _run_single(
        self,
        parameters=None,
        *,
        observations: Concentrations | None = None,
    ) -> LpmSampleTable:
        """Run one Nelder-Mead optimization."""
        calibration_observations = (
            self.observations if observations is None else observations
        )
        initial = self.lpm.param_init() if parameters is None else parameters
        observed, errors = self.observation_arrays(calibration_observations)
        bounds = list(zip(*self.lpm.get_param_interval(), strict=True))
        optimization = minimize(
            self.objective_function,
            initial,
            args=(observed, errors),
            method="nelder-mead",
            bounds=bounds,
            options={
                "xatol": self.x_tolerance,
                "fatol": self.function_tolerance,
                "disp": False,
            },
        )
        if not optimization.success:
            raise RuntimeError(
                "Nelder-Mead calibration did not converge: "
                f"status={optimization.status}, message={optimization.message}"
            )

        optimum = np.asarray(optimization.x, dtype=float)
        if not np.all(np.isfinite(optimum)) or not self.lpm.param_within_bounds_array(
            optimum
        ):
            raise RuntimeError(
                f"Nelder-Mead returned invalid parameters: {optimum.tolist()}"
            )
        chi_square, concentrations = self.objective_function(
            optimum,
            observed,
            errors,
            conc=True,
        )
        if not np.isfinite(chi_square):
            raise RuntimeError("Nelder-Mead returned a non-finite objective value")
        if not np.isclose(chi_square, optimization.fun, rtol=1e-10, atol=1e-12):
            raise RuntimeError(
                "Nelder-Mead result is inconsistent with a fresh objective evaluation: "
                f"reported={optimization.fun}, recomputed={chi_square}"
            )
        self._optimization_runs.append(
            {
                "status": int(optimization.status),
                "iterations": int(optimization.nit),
                "evaluations": int(optimization.nfev),
                "chi_square": float(chi_square),
            }
        )
        results = LpmSampleTable(
            self.lpm,
            c_names=calibration_observations.observation_keys(),
        )
        results.append_sample(
            self.lpm.p.copy(),
            obj_function=normalized_residual_norm(
                chi_square, len(calibration_observations.frame)
            ),
            concentrations=concentrations,
            param_in_bounds=True,
        )
        return results

    def _run_multiple(self) -> LpmSampleTable:
        """Run Nelder-Mead from several reproducible random starts."""
        results = LpmSampleTable(self.lpm, c_names=self.observations.observation_keys())
        rng = np.random.default_rng(self.initialization_seed)
        for _ in range(self.initialization_count):
            self.lpm.random_uniform(rng=rng)
            results.append(self._run_single(self.lpm.get_parameters_to_array()))
        return results

    def _run_forward_uncertainty(self) -> LpmSampleTable:
        """Calibrate several observation draws within measurement errors."""
        results = LpmSampleTable(self.lpm, c_names=self.observations.observation_keys())
        uncertainty_rng = np.random.default_rng(self.uncertainty_seed)
        initialization_rng = np.random.default_rng(self.initialization_seed)
        for _ in range(self.uncertainty_sample_count):
            sampled_observations = self.observations.sample_with_errors(uncertainty_rng)
            for _ in range(self.initialization_count):
                if self.initialization_count == 1:
                    initial = self.lpm.param_init()
                else:
                    self.lpm.random_uniform(rng=initialization_rng)
                    initial = self.lpm.get_parameters_to_array()
                results.append(
                    self._run_single(initial, observations=sampled_observations)
                )
        return results

    def write_parameters(self, file_name: str | Path) -> None:
        """Write the selected Simplex settings."""
        values: dict[str, Any] = {
            "method": self.method,
            "xatol": self.x_tolerance,
            "fatol": self.function_tolerance,
        }
        if self.method in {MULTI_START, FORWARD_UNCERTAINTY}:
            values["initialization_count"] = self.initialization_count
            values["initialization_seed"] = self.initialization_seed
        if self.method == FORWARD_UNCERTAINTY:
            values["fuq_n"] = self.uncertainty_sample_count
            values["uncertainty_seed"] = self.uncertainty_seed
        write_key_values(file_name, values)

    def write_results_spec(self, data: dict[str, Any]) -> None:
        """Record aggregate optimizer termination diagnostics."""
        data["optimization_run_count"] = len(self._optimization_runs)
        data["optimization_all_converged"] = bool(self._optimization_runs)
        data["optimization_iterations_total"] = sum(
            run["iterations"] for run in self._optimization_runs
        )
        data["optimization_evaluations_total"] = sum(
            run["evaluations"] for run in self._optimization_runs
        )


__all__ = [
    "FORWARD_UNCERTAINTY",
    "MULTI_START",
    "SIMPLEX",
    "Simplex",
]
