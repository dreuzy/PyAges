"""Nelder-Mead calibration methods."""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from pyage.calibration.methods.base import CalibrationMethod
from pyage.calibration.outputs import write_key_values
from pyage.calibration.utils.objective_functions import normalized_residual_norm
from pyage.concentrations.schema import CONCENTRATION_COLUMN, ERROR_COLUMN
from pyage.lpm.core.lpm_dist import LpmDist

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
        super().__init__()
        if calibration_method not in VALID_METHODS:
            raise ValueError(
                f"Unknown simplex calibration method: {calibration_method}"
            )
        self.method = calibration_method
        self.x_tolerance = 1e-8
        self.function_tolerance = 1e-8
        self.initialization_count = init_multiples_n
        self.initialization_seed = 12345
        self.uncertainty_seed = 123456
        self.uncertainty_sample_count = fuq_n

    def perform(self) -> LpmDist:
        """Execute the configured Simplex variant on the bound problem."""
        start = time.time()
        if self.method == SIMPLEX:
            results = self._run_single()
        elif self.method == MULTI_START:
            results = self._run_multiple()
        else:
            results = self._run_forward_uncertainty()
        self.time_perform = time.time() - start
        return results.add_moments()

    def _run_single(self, parameters=None) -> LpmDist:
        """Run one Nelder-Mead optimization."""
        initial = self.lpm.param_init() if parameters is None else parameters
        optimization = minimize(
            self.objective_function,
            initial,
            args=(
                self.observations.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float),
                self.observations.cv[ERROR_COLUMN].to_numpy(dtype=float),
            ),
            method="nelder-mead",
            options={
                "xatol": self.x_tolerance,
                "fatol": self.function_tolerance,
                "disp": False,
            },
        )
        results = LpmDist(self.lpm, c_names=self.observations.names_dates())
        results.append_sample(
            self.lpm.p,
            obj_function=normalized_residual_norm(
                optimization.fun, len(self.observations.cv)
            ),
            concentrations=self.tracers.convolve(self.lpm),
            param_in_bounds=self.lpm.param_within_bounds(self.lpm.p),
        )
        return results

    def _run_multiple(self) -> LpmDist:
        """Run Nelder-Mead from several reproducible random starts."""
        results = LpmDist(self.lpm, c_names=self.observations.names_dates())
        rng = np.random.default_rng(self.initialization_seed)
        for _ in range(self.initialization_count):
            self.lpm.random_uniform(rng=rng)
            results.append(self._run_single(self.lpm.get_parameters_to_array()))
        return results

    def _run_forward_uncertainty(self) -> LpmDist:
        """Calibrate several observation draws within measurement errors."""
        results = LpmDist(self.lpm, c_names=self.observations.names_dates())
        sampled_method = copy.deepcopy(self)
        sampled_method.method = MULTI_START
        uncertainty_rng = np.random.default_rng(self.uncertainty_seed)
        initialization_rng = np.random.default_rng(self.initialization_seed)
        for _ in range(self.uncertainty_sample_count):
            sampled_method.problem.observations = (
                self.observations.sample_concentrations_with_errors(uncertainty_rng)
            )
            for _ in range(self.initialization_count):
                if self.initialization_count == 1:
                    self.lpm.param_init()
                else:
                    self.lpm.random_uniform(rng=initialization_rng)
                results.append(
                    sampled_method._run_single(self.lpm.get_parameters_to_array())
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
        if self.method == FORWARD_UNCERTAINTY:
            values["fuq_n"] = self.uncertainty_sample_count
        write_key_values(file_name, values)

    def write_results_spec(self, data: dict[str, Any]) -> None:
        """Simplex currently has no additional scalar run result."""


__all__ = [
    "FORWARD_UNCERTAINTY",
    "MULTI_START",
    "SIMPLEX",
    "Simplex",
]
