# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Failure, repeated-start, and serialization contracts for Simplex."""

from __future__ import annotations

from types import MethodType, SimpleNamespace

import numpy as np
import pytest

from pyages.calibration.methods.simplex import (
    FORWARD_UNCERTAINTY,
    MULTI_START,
    SIMPLEX,
    Simplex,
)
from pyages.lpm.samples.table import LpmSampleTable
from tests.calibration.test_calibration_problem import _prepared_problem


def test_simplex_rejects_an_unknown_execution_mode() -> None:
    with pytest.raises(ValueError, match="Unknown simplex calibration method"):
        Simplex("unsupported")


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"init_multiples_n": 0}, "init_multiples_n"),
        ({"init_multiples_n": True}, "init_multiples_n"),
        ({"fuq_n": -1}, "fuq_n"),
    ],
)
def test_simplex_rejects_invalid_run_counts(options, message) -> None:
    with pytest.raises(ValueError, match=message):
        Simplex(FORWARD_UNCERTAINTY, **options)


@pytest.mark.parametrize("optimum", [[np.nan], [1.0e30]])
def test_simplex_rejects_nonfinite_or_out_of_bounds_optimum(
    tmp_path, monkeypatch, optimum
) -> None:
    problem = _prepared_problem(tmp_path)
    optimization = SimpleNamespace(
        success=True,
        status=0,
        message="converged",
        x=np.asarray(optimum),
        fun=0.0,
        nit=1,
        nfev=2,
    )
    monkeypatch.setattr(
        "pyages.calibration.methods.simplex.minimize",
        lambda *_args, **_kwargs: optimization,
    )

    with pytest.raises(RuntimeError, match="returned invalid parameters"):
        Simplex(SIMPLEX).run(problem)


def test_simplex_rejects_an_inconsistent_reported_objective(
    tmp_path, monkeypatch
) -> None:
    problem = _prepared_problem(tmp_path)
    optimum = np.asarray(problem.lpm.param_init(), dtype=float)

    def fake_minimize(objective, _initial, *, args, **_kwargs):
        actual = objective(optimum, *args)
        return SimpleNamespace(
            success=True,
            status=0,
            message="converged",
            x=optimum,
            fun=actual + 1.0,
            nit=1,
            nfev=2,
        )

    monkeypatch.setattr("pyages.calibration.methods.simplex.minimize", fake_minimize)

    with pytest.raises(RuntimeError, match="inconsistent with a fresh objective"):
        Simplex(SIMPLEX).run(problem)


def _recording_single_run(captured):
    def fake_run_single(self, parameters=None, *, observations=None):
        source = self.observations if observations is None else observations
        values = np.asarray(parameters, dtype=float)
        captured.append(tuple(values))
        sample = LpmSampleTable(self.lpm, c_names=source.observation_keys())
        sample.append_sample(
            dict(zip(self.lpm.get_param_names(), values, strict=True)),
            obj_function=0.0,
            concentrations=source.frame["concentration"].to_numpy(),
            param_in_bounds=True,
        )
        self._optimization_runs.append(
            {"status": 0, "iterations": 2, "evaluations": 4, "chi_square": 0.0}
        )
        return sample

    return fake_run_single


def _multi_start_sequence(problem, count):
    captured = []
    method = Simplex(MULTI_START, init_multiples_n=count)
    method._bind_problem(problem)
    method._run_single = MethodType(_recording_single_run(captured), method)

    results = method._run_multiple()

    return captured, results


def test_simplex_multi_start_is_reproducible_and_runs_every_start(tmp_path) -> None:
    problem = _prepared_problem(tmp_path)

    first_starts, first_results = _multi_start_sequence(problem, 3)
    second_starts, second_results = _multi_start_sequence(problem, 3)

    assert first_starts == second_starts
    assert len(first_starts) == 3
    assert len(set(first_starts)) == 3
    assert len(first_results.frame) == len(second_results.frame) == 3


def test_forward_uncertainty_runs_the_cartesian_sample_and_start_count(
    tmp_path, monkeypatch
) -> None:
    problem = _prepared_problem(tmp_path)
    captured = []
    monkeypatch.setattr(Simplex, "_run_single", _recording_single_run(captured))
    method = Simplex(FORWARD_UNCERTAINTY, init_multiples_n=2, fuq_n=3)
    method._bind_problem(problem)

    results = method._run_forward_uncertainty()

    assert len(captured) == 6
    assert len(results.frame) == 6
    assert len(method._optimization_runs) == 6


def test_forward_uncertainty_keeps_the_bound_problem_and_original_observations(
    tmp_path, monkeypatch
) -> None:
    problem = _prepared_problem(tmp_path)
    original_observations = problem.observations
    sampled_inputs = []

    def fake_run_single(self, parameters=None, *, observations=None):
        assert self.problem is problem
        sampled_inputs.append(observations)
        return _recording_single_run([])(
            self,
            parameters,
            observations=observations,
        )

    monkeypatch.setattr(Simplex, "_run_single", fake_run_single)
    method = Simplex(FORWARD_UNCERTAINTY, init_multiples_n=1, fuq_n=2)
    method._bind_problem(problem)

    method._run_forward_uncertainty()

    assert problem.observations is original_observations
    assert len(sampled_inputs) == 2
    assert all(sampled is not original_observations for sampled in sampled_inputs)


def test_simplex_serializes_variant_settings_and_optimizer_totals(tmp_path) -> None:
    method = Simplex(FORWARD_UNCERTAINTY, init_multiples_n=3, fuq_n=4)
    method._optimization_runs = [
        {"iterations": 2, "evaluations": 5},
        {"iterations": 3, "evaluations": 7},
    ]
    parameters = tmp_path / "simplex-parameters.txt"
    method.write_parameters(parameters)
    diagnostics = {}

    method.write_results_spec(diagnostics)

    contents = parameters.read_text(encoding="utf-8")
    assert "method\tforward_uncertainty_quantification" in contents
    assert "initialization_count\t3" in contents
    assert "fuq_n\t4" in contents
    assert diagnostics == {
        "optimization_run_count": 2,
        "optimization_all_converged": True,
        "optimization_iterations_total": 5,
        "optimization_evaluations_total": 12,
    }
