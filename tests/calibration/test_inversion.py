# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public deterministic inversion contracts."""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from pyages.calibration import CalibrationProblem, ObjectiveSpec, invert_lpm
from pyages.concentrations import Concentrations
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm


def _synthetic_problem(mu: float = 25.0) -> CalibrationProblem:
    target = build_lpm("exp")
    target.set_param_from_array([mu])
    tracers = ConvolutionTracers(
        names=["cfc11", "cfc12"],
        date=[2010.0, 2010.0],
    )
    generated = tracers.convolve(target, return_type="concentrations")
    generated.set_relative_errors(0.05)
    observations = Concentrations.from_dataframe(generated.frame)
    return CalibrationProblem(
        observations,
        "exp",
        explore_objective=False,
        explore_reachable=False,
    ).prepare()


def test_default_inversion_preserves_problem_and_reports_cross_metrics() -> None:
    problem = _synthetic_problem()
    committed = problem.lpm.get_parameters_to_array()

    result = invert_lpm(problem)

    assert result.success
    assert result.objective == ObjectiveSpec.pyages_default()
    assert result.objective.name == "uncertainty_l2"
    assert result.parameters["mu"] == pytest.approx(25.0, rel=2e-4)
    assert result.objective_value == pytest.approx(result.metrics["chi_square"])
    assert result.objective_name == "uncertainty_l2"
    assert result.chi_square == pytest.approx(result.objective_value)
    assert result.normalized_residual_rms == pytest.approx(
        np.sqrt(result.chi_square / len(result.residuals))
    )
    assert result.metrics["relative_l1"] >= 0.0
    assert len(result.residuals) == 2
    assert all(record.observation_key for record in result.residuals)
    assert result.target_sha256 == problem.target_signature().sha256
    assert problem.lpm.get_parameters_to_array() == committed


def test_relative_l1_and_l2_use_the_same_forward_target() -> None:
    problem = _synthetic_problem()
    starts = [{"mu": 8.0}, {"mu": 60.0}]

    l1 = invert_lpm(
        problem,
        objective=ObjectiveSpec.relative_l1(),
        starts=starts,
    )
    l2 = invert_lpm(
        problem,
        objective=ObjectiveSpec.relative_l2(),
        starts=starts,
    )

    assert l1.success and l2.success
    assert l1.target_sha256 == l2.target_sha256
    assert l1.optimizer == l2.optimizer == "powell"
    assert [dict(attempt.initial_parameters) for attempt in l1.attempts] == [
        dict(attempt.initial_parameters) for attempt in l2.attempts
    ]
    assert l1.parameters["mu"] == pytest.approx(25.0, rel=2e-4)
    assert l2.parameters["mu"] == pytest.approx(25.0, rel=2e-4)
    assert l1.objective_value == pytest.approx(l1.metrics["relative_l1"])
    assert l2.objective_value == pytest.approx(l2.metrics["relative_l2_squared"])


def test_result_residuals_recompute_from_selected_solution() -> None:
    problem = _synthetic_problem(mu=32.0)
    result = invert_lpm(
        problem,
        objective=ObjectiveSpec(loss="l1", scale="uncertainty"),
        starts=[[12.0]],
    )

    observed, errors = problem.prepared_observation_arrays()
    modeled = np.asarray([record.modeled for record in result.residuals])
    expected = modeled - observed
    np.testing.assert_allclose(
        [record.residual for record in result.residuals], expected
    )
    np.testing.assert_allclose(
        [record.standardized_residual for record in result.residuals],
        expected / errors,
    )


def test_result_has_detached_strict_json_representation() -> None:
    result = invert_lpm(_synthetic_problem(), starts=[{"mu": 12.0}])

    payload = result.to_dict()
    encoded = json.dumps(payload, allow_nan=False)

    assert '"name": "uncertainty_l2"' in encoded
    assert payload["objective_name"] == "uncertainty_l2"
    assert payload["loss"] == "l2"
    assert payload["scale"] == "uncertainty"
    assert payload["chi_square"] == pytest.approx(payload["objective_value"])
    assert payload["obj_function"] == pytest.approx(
        payload["normalized_residual_rms"]
    )
    assert payload["parameters"] == {"mu": pytest.approx(25.0, rel=2e-4)}
    assert payload["attempts"][0]["initial_parameters"] == {"mu": 12.0}
    payload["parameters"]["mu"] = -1.0
    assert result.parameters["mu"] == pytest.approx(25.0, rel=2e-4)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"optimizer": "unknown"}, "optimizer"),
        ({"starts": []}, "at least one"),
        ({"starts": [[1.0, 2.0]]}, "Expected 1"),
        ({"starts": [{"wrong": 1.0}]}, "exactly match"),
        ({"starts": [[-1.0]]}, "calibration range"),
        ({"starts": [["not-a-number"]]}, "numeric"),
        ({"starts": [[np.inf]]}, "finite"),
        ({"objective": "relative_l1"}, "ObjectiveSpec"),
    ],
)
def test_inversion_rejects_invalid_controls(kwargs, message) -> None:
    problem = _synthetic_problem()

    with pytest.raises((TypeError, ValueError), match=message):
        invert_lpm(problem, **kwargs)


def test_inversion_requires_a_prepared_problem() -> None:
    prepared = _synthetic_problem()
    unprepared = CalibrationProblem(
        Concentrations.from_dataframe(prepared.observations.frame),
        "exp",
        explore_objective=False,
        explore_reachable=False,
    )

    with pytest.raises(RuntimeError, match="initialize"):
        invert_lpm(unprepared)


def test_finite_failed_optimizer_result_remains_auditable(monkeypatch) -> None:
    problem = _synthetic_problem()

    def fail_with_finite_candidate(*args, **kwargs):
        return SimpleNamespace(
            x=np.asarray([25.0]),
            success=False,
            status=2,
            message="iteration limit",
            nit=4,
            nfev=8,
        )

    monkeypatch.setattr(
        "pyages.calibration.inversion.minimize", fail_with_finite_candidate
    )
    result = invert_lpm(problem)

    assert not result.success
    assert result.parameters["mu"] == pytest.approx(25.0)
    assert result.attempts[0].parameters is not None
    assert result.attempts[0].status == 2
    assert result.attempts[0].message == "iteration limit"


def test_optimizer_options_merge_defaults_and_remain_detached(monkeypatch) -> None:
    problem = _synthetic_problem()
    captured = {}

    def capture_options(objective, initial, *, method, bounds, options):
        captured.update(method=method, bounds=bounds, options=dict(options))
        return SimpleNamespace(
            x=np.asarray([25.0]),
            success=True,
            status=0,
            message="converged",
            nit=2,
            nfev=3,
        )

    monkeypatch.setattr("pyages.calibration.inversion.minimize", capture_options)
    caller_options = {"maxiter": 7}

    result = invert_lpm(problem, options=caller_options)
    caller_options["maxiter"] = 99

    assert captured["method"] == "Powell"
    assert captured["options"]["maxiter"] == 7
    assert captured["options"]["xtol"] == pytest.approx(1e-8)
    assert result.optimizer_options["maxiter"] == 7


@pytest.mark.parametrize(
    "candidate",
    [np.asarray([1.0, 2.0]), object()],
    ids=["wrong-shape", "not-numeric"],
)
def test_malformed_optimizer_candidate_raises_clean_error(
    monkeypatch, candidate
) -> None:
    problem = _synthetic_problem()

    def return_malformed_candidate(*args, **kwargs):
        return SimpleNamespace(
            x=candidate,
            success=True,
            status=0,
            message="malformed candidate",
            nit=1,
            nfev=1,
        )

    monkeypatch.setattr(
        "pyages.calibration.inversion.minimize", return_malformed_candidate
    )

    with pytest.raises(RuntimeError, match="Every inversion attempt"):
        invert_lpm(problem)
