"""Characterization tests for the explicit calibration composition."""

from __future__ import annotations

import numpy as np
import pytest

from pyage.calibration.methods.simplex import SIMPLEX, Simplex
from pyage.calibration.problem import CalibrationProblem
from pyage.calibration.utils.systematic_sampling import SystematicSampling
from pyage.config.runtime import DisplayOptions
from pyage.convolution import ConvolutionTracers
from pyage.lpm.lpm_build import lpm_build


def _prepared_problem(tmp_path) -> CalibrationProblem:
    target = lpm_build("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.error_affect_from_value(0.05)
    display = DisplayOptions()
    display.figure = False
    display.text = False
    display.directory = tmp_path
    return CalibrationProblem(
        observations,
        "exp",
        display_options=display,
        sample_count=9,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()


def test_problem_uses_composition_and_preserves_the_target_objective(tmp_path):
    problem = _prepared_problem(tmp_path)

    assert not isinstance(problem, SystematicSampling)
    assert isinstance(problem.sampling, SystematicSampling)
    objective, modeled = problem.objective_function(
        problem.lpm.get_parameters_to_array(),
        problem.observations.cv["concentration"].to_numpy(dtype=float),
        problem.observations.cv["error"].to_numpy(dtype=float),
        return_concentrations=True,
    )

    assert objective == pytest.approx(0.0, abs=1e-12)
    assert np.allclose(modeled, problem.observations.cv["concentration"])


def test_method_is_bound_explicitly_to_the_problem(tmp_path):
    problem = _prepared_problem(tmp_path)
    method = Simplex(SIMPLEX)

    results = method.run(problem)

    assert method.problem is problem
    assert len(results.dist()) == 1
    assert np.isfinite(results.best_row()["obj_function"])


def test_problem_rejects_non_positive_observation_errors(tmp_path):
    problem = _prepared_problem(tmp_path)

    with pytest.raises(ValueError, match="strictly positive"):
        problem.objective_function(
            problem.lpm.get_parameters_to_array(),
            np.array([1.0]),
            np.array([0.0]),
        )
