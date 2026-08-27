# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Characterization tests for the explicit calibration composition."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from pyages.calibration.methods.simplex import SIMPLEX, Simplex
from pyages.calibration.problem import CalibrationProblem
from pyages.calibration.utils.systematic_sampling import SystematicSampling
from pyages.concentrations import Concentrations
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm


def _prepared_problem(tmp_path) -> CalibrationProblem:
    target = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.05)
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
    assert problem.sampling is problem.sampling
    objective, modeled = problem.objective_function(
        problem.lpm.get_parameters_to_array(),
        problem.observations.frame["concentration"].to_numpy(dtype=float),
        problem.observations.frame["error"].to_numpy(dtype=float),
        return_concentrations=True,
    )

    assert objective == pytest.approx(0.0, abs=1e-12)
    assert np.allclose(modeled, problem.observations.frame["concentration"])


def test_objective_loop_does_not_repeat_unit_validation(tmp_path):
    problem = _prepared_problem(tmp_path)
    parameters = problem.lpm.get_parameters_to_array()
    observed = problem.observations.frame["concentration"].to_numpy(dtype=float)
    errors = problem.observations.frame["error"].to_numpy(dtype=float)

    with patch.object(
        problem.observations,
        "require_matching_units",
        side_effect=AssertionError("unit validation leaked into objective loop"),
    ):
        problem.objective_function(parameters, observed, errors)
        problem.objective_function(parameters, observed, errors)


def test_systematic_exploration_is_built_only_when_requested(tmp_path):
    with patch("pyages.calibration.problem.SystematicSampling") as sampling_class:
        problem = _prepared_problem(tmp_path)
        sampling_class.assert_not_called()

        sampling = problem.sampling

        sampling_class.assert_called_once()
        assert problem.sampling is sampling


def test_method_is_bound_explicitly_to_the_problem(tmp_path):
    problem = _prepared_problem(tmp_path)
    method = Simplex(SIMPLEX)

    results = method.run(problem)

    assert method.problem is problem
    assert len(results.frame) == 1
    assert np.isfinite(results.best_row()["obj_function"])


def test_problem_rejects_non_positive_observation_errors(tmp_path):
    problem = _prepared_problem(tmp_path)

    with pytest.raises(ValueError, match="strictly positive"):
        problem.objective_function(
            problem.lpm.get_parameters_to_array(),
            np.array([1.0]),
            np.array([0.0]),
        )


def test_problem_rejects_observation_model_unit_mismatch_before_calibration(
    tmp_path,
):
    observations = Concentrations.from_dataframe(
        _prepared_problem(tmp_path).observations.frame.assign(unit="pmol/kg")
    )
    problem = CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    )

    with pytest.raises(
        ValueError, match="observations use 'pmol/kg'.*model uses 'pptv'"
    ):
        problem.prepare()
