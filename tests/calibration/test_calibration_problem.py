# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Characterization tests for the explicit calibration composition."""

from __future__ import annotations

import shutil
from copy import deepcopy
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import yaml

from pyages.calibration.exploration.systematic import SystematicSampling
from pyages.calibration.methods.simplex import SIMPLEX, Simplex
from pyages.calibration.problem import CalibrationProblem, resolve_observation_errors
from pyages.concentrations import Concentrations
from pyages.config.paths import DIRECTORY_LPM_DATA
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


def test_scientific_target_signature_is_stable_across_display_paths(tmp_path) -> None:
    first = _prepared_problem(tmp_path / "first")
    second = _prepared_problem(tmp_path / "second")

    first_signature = first.target_signature()
    second_signature = second.target_signature()

    assert first_signature == second_signature
    assert first_signature.sha256 == second_signature.sha256
    assert len(first_signature.sha256) == 64
    assert first_signature.differing_category(second_signature) is None


def test_lpm_document_signature_ignores_yaml_formatting_and_source_path(
    tmp_path,
) -> None:
    first_root = tmp_path / "first_lpm_root"
    second_root = tmp_path / "second_lpm_root"
    shutil.copytree(DIRECTORY_LPM_DATA / "exp", first_root / "exp")
    shutil.copytree(DIRECTORY_LPM_DATA / "exp", second_root / "exp")
    second_path = second_root / "exp" / "params.yaml"
    parsed = yaml.safe_load(second_path.read_text(encoding="utf-8"))
    second_path.write_text(
        "# Semantically identical document with different formatting.\n"
        + yaml.safe_dump(parsed, sort_keys=True),
        encoding="utf-8",
    )

    target = build_lpm("exp")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.05)
    first = CalibrationProblem(
        Concentrations.from_dataframe(observations.frame),
        "exp",
        lpm_directory=first_root,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    second = CalibrationProblem(
        Concentrations.from_dataframe(observations.frame),
        "exp",
        lpm_directory=second_root,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()

    assert first.target_signature() == second.target_signature()


def test_lpm_fixed_scientific_state_is_part_of_the_signature() -> None:
    target = build_lpm("dirac_double_1_set")
    tracers = ConvolutionTracers(names=["cfc11"], date=2010.0)
    observations = tracers.convolve(target, return_type="concentrations")
    observations.set_relative_errors(0.05)
    first = CalibrationProblem(
        Concentrations.from_dataframe(observations.frame),
        "dirac_double_1_set",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    second = CalibrationProblem(
        Concentrations.from_dataframe(observations.frame),
        "dirac_double_1_set",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    second.lpm._DiracDouble1SetLpm__muset = 71.0  # noqa: SLF001

    assert (
        first.target_signature().differing_category(second.target_signature()) == "lpm"
    )


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


def test_problem_preparation_is_atomic_when_tracer_preparation_fails(tmp_path):
    problem = _prepared_problem(tmp_path)
    observations = Concentrations.from_dataframe(problem.observations.frame)
    failing = CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    )

    with patch.object(
        ConvolutionTracers,
        "prepare",
        side_effect=RuntimeError("prepared grid failed"),
    ):
        with pytest.raises(RuntimeError, match="prepared grid failed"):
            failing.prepare()

    assert failing.is_prepared is False
    assert failing.lpm is None
    assert failing.tracers is None
    with pytest.raises(RuntimeError, match="initialize"):
        failing.ensure_prepared()


def test_problem_rejects_observation_mutation_after_preparation(tmp_path):
    problem = _prepared_problem(tmp_path)
    problem.observations.frame.loc[0, "concentration"] += 1.0

    with pytest.raises(RuntimeError, match="Observations changed"):
        problem.ensure_prepared()


def test_candidate_objective_does_not_mutate_committed_lpm(tmp_path):
    problem = _prepared_problem(tmp_path)
    committed = problem.lpm.get_parameters_to_array()
    candidate = deepcopy(problem.lpm)
    observed, errors = problem.prepared_observation_arrays()

    problem.objective_function_for_lpm(
        candidate,
        [20.0],
        observed,
        errors,
    )

    assert problem.lpm.get_parameters_to_array() == committed
    assert candidate.get_parameters_to_array() == [20.0]


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


def test_missing_errors_use_each_observation_sampling_date(tmp_path) -> None:
    target = build_lpm("exp")
    source_tracers = ConvolutionTracers(
        names=["cfc11", "cfc11"],
        date=[1990.0, 2010.0],
    )
    observations = source_tracers.convolve(target, return_type="concentrations")

    display = DisplayOptions()
    display.directory = tmp_path
    problem = CalibrationProblem(
        observations,
        "exp",
        display_options=display,
        missing_error_relative_fraction=0.05,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()

    expected = 0.05 * np.asarray(
        problem.tracers.mean_values_at_sampling_dates(), dtype=float
    )
    actual = observations.frame["error"].to_numpy(dtype=float)
    np.testing.assert_allclose(actual, expected)
    assert expected[0] != pytest.approx(expected[1])
    assert observations.error_provenance[0]["fraction"] == 0.05


def test_resolved_observation_errors_must_be_strictly_positive() -> None:
    observations = Concentrations.from_dataframe(
        pd.DataFrame(
            {
                "element": ["cfc11"],
                "concentration": [0.0],
                "error": [0.0],
                "unit": ["pptv"],
                "date": [2010.0],
            }
        )
    )
    tracers = patch("pyages.calibration.problem.ConvolutionTracers")
    with tracers as tracer_class:
        tracer_class.return_value.mean_values_at_sampling_dates.return_value = [0.0]
        with pytest.raises(ValueError, match="strictly positive"):
            resolve_observation_errors(observations)


def test_disabled_systematic_analysis_performs_no_convolution(tmp_path) -> None:
    display = DisplayOptions()
    display.directory = tmp_path
    sampling = SystematicSampling(
        "exp",
        ["cfc11"],
        sample_count=2,
        explore_objective=False,
        explore_reachable=False,
        display_options=display,
    )

    with patch.object(
        sampling,
        "compute_concentrations",
        side_effect=AssertionError("disabled exploration performed convolution"),
    ):
        sampling.analysis_calibration()


def test_systematic_output_reports_actual_and_target_grid_sizes(tmp_path) -> None:
    display = DisplayOptions()
    display.directory = tmp_path
    sampling = SystematicSampling(
        "exp",
        ["cfc11"],
        sample_count=2,
        explore_objective=False,
        explore_reachable=True,
        display_options=display,
    )

    sampling.compute_concentrations()
    sampling.output()

    metadata = (tmp_path / "parameters.txt").read_text(encoding="utf-8")
    assert "nmodels\t3\n" in metadata
    assert "target_nmodels\t2\n" in metadata
