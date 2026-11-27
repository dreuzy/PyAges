# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file evaluates proposed parameters on a private model copy, preventing a
# rejected proposal from changing the model state owned by the calibration run.

"""Evaluate MH candidates without mutating the committed calibration LPM."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import numpy as np


class MHTarget:
    """Own one private working LPM used only for candidate evaluations."""

    def __init__(self, problem: Any, prior: Any, *, likelihood: bool) -> None:
        """Create one detached candidate model for a prepared problem."""
        problem.ensure_prepared()
        if problem.lpm is None:
            raise RuntimeError("A prepared calibration problem must expose an LPM")
        self._problem = problem
        self._prior = prior
        self._likelihood = likelihood
        self._candidate_lpm = deepcopy(problem.lpm)

    @property
    def candidate_lpm(self) -> Any:
        """Return the private model for diagnostics and invariant tests."""
        return self._candidate_lpm

    def evaluate(
        self,
        params: list[float],
        observed: np.ndarray,
        errors: np.ndarray,
    ) -> tuple[float, float, list[float]]:
        """Return log target, chi-square, and modeled concentrations."""
        if self._candidate_lpm.param_within_calibration_range_array(params) is False:
            return -math.inf, math.inf, []

        log_probability = 0.0
        if self._likelihood:
            chi_square, concentrations = self._problem.objective_function_for_lpm(
                self._candidate_lpm,
                params,
                observed,
                errors,
                return_concentrations=True,
            )
            log_probability -= 0.5 * chi_square
        else:
            # Keep the private candidate synchronized even when no forward
            # calculation is required by the target.
            self._candidate_lpm.set_param_from_array(params)
            chi_square = 0.0
            concentrations = [math.nan] * len(observed)

        if self._prior.option:
            log_probability += self._prior.log_evaluate(
                self._candidate_lpm,
                params,
            )
        return log_probability, chi_square, list(concentrations)


__all__ = ["MHTarget"]
