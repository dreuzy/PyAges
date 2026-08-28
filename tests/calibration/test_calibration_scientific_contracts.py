# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Regression tests for calibration result and monitoring contracts."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pyages.calibration.methods.mh import MetropolisHastings, MHConfig
from pyages.calibration.methods.mh.trajectory import MHTrajectory
from pyages.calibration.methods.simplex import SIMPLEX, Simplex
from tests.calibration.test_calibration_mh_initial_params import _FakeLpm
from tests.calibration.test_calibration_problem import _prepared_problem


def test_simplex_persists_the_reported_optimum_as_one_joint_sample(
    tmp_path, monkeypatch
):
    problem = _prepared_problem(tmp_path)
    optimum = np.asarray(problem.lpm.param_init(), dtype=float)
    last_evaluated = optimum + 5.0
    captured: dict[str, object] = {}

    def fake_minimize(objective, _initial, *, args, method: str, bounds, options):
        assert method == "nelder-mead"
        assert options["disp"] is False
        captured["bounds"] = bounds
        objective(last_evaluated, *args)
        value = objective(optimum, *args)
        return SimpleNamespace(
            success=True,
            status=0,
            message="converged",
            x=optimum,
            fun=value,
            nit=4,
            nfev=8,
        )

    monkeypatch.setattr("pyages.calibration.methods.simplex.minimize", fake_minimize)
    result = Simplex(SIMPLEX).run(problem)
    row = result.frame.iloc[0]

    assert captured["bounds"] == list(
        zip(*problem.lpm.get_param_interval(), strict=True)
    )
    assert row["mu"] == pytest.approx(optimum[0])
    assert row["obj_function"] == pytest.approx(0.0, abs=1e-12)
    assert row[problem.observations.observation_keys()[0]] == pytest.approx(
        problem.observations.frame["concentration"].iloc[0]
    )


def test_simplex_rejects_an_optimizer_failure(tmp_path, monkeypatch):
    problem = _prepared_problem(tmp_path)

    def fake_minimize(*_args, **_kwargs):
        return SimpleNamespace(success=False, status=2, message="maximum iterations")

    monkeypatch.setattr("pyages.calibration.methods.simplex.minimize", fake_minimize)
    with pytest.raises(RuntimeError, match="did not converge"):
        Simplex(SIMPLEX).run(problem)


def test_explicit_initial_state_takes_precedence_over_prior_map(monkeypatch):
    mh = MetropolisHastings(
        MHConfig(
            prior_option=True,
            likelihood=False,
            initial_params={"mu": 35.0, "shift": 20.0},
        )
    )
    problem = SimpleNamespace(lpm=_FakeLpm(), ensure_prepared=lambda: None)
    mh._bind_problem(problem)
    monkeypatch.setattr(
        mh.prior,
        "param_init",
        lambda *_args, **_kwargs: pytest.fail(
            "prior MAP must not replace initial_params"
        ),
    )
    monkeypatch.setattr(mh.prior, "log_evaluate", lambda *_args: 0.0)

    params, *_ = mh._initialize_state(  # noqa: SLF001
        np.array([]), np.array([])
    )

    assert params == [35.0, 20.0]


def test_trajectory_records_negative_log_posterior_and_acceptance_state():
    trajectory = MHTrajectory(["mu"], 2)

    trajectory.update(0, [10.0], -3.5, accepted=False)
    trajectory.update(1, [11.0], -2.0, accepted=True)

    assert trajectory.path["-log_posterior"].tolist() == [3.5, 2.0]
    assert trajectory.path["incrementation"].tolist() == [0, 1]
    summary = trajectory.summary()
    assert summary.loc["mu", "mean"] == pytest.approx(10.5)
    assert summary.loc["mu", "std"] == pytest.approx(0.5)
    pd.testing.assert_frame_equal(trajectory.check(), summary)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"nstep": 0}, "nstep"),
        ({"burn_in": 1.0}, "burn_in"),
        ({"nskip": 0}, "nskip"),
        ({"prior_type": "unknown"}, "prior_type"),
        ({"proposal_kind": "unknown"}, "proposal_kind"),
        ({"componentwise_fraction": 0.0}, "componentwise_fraction"),
        ({"proposal_multiplier": 0.0}, "proposal_multiplier"),
        (
            {"proposal_scales": (1.0,)},
            "componentwise proposals do not accept",
        ),
        (
            {"proposal_kind": "diagonal"},
            "diagonal requires proposal_scales",
        ),
        (
            {"proposal_kind": "correlated"},
            "correlated requires proposal_covariance",
        ),
        (
            {"nstep": 5, "burn_in": 0.9, "nskip": 5},
            "retain no samples",
        ),
    ],
)
def test_mh_config_rejects_invalid_scientific_controls(kwargs, message):
    with pytest.raises(ValueError, match=message):
        MHConfig(**kwargs)


def test_mh_retained_sample_count_matches_the_documented_rule() -> None:
    config = MHConfig(nstep=17, burn_in=0.2, nskip=3)
    retained = [
        iteration
        for iteration in range(config.nstep)
        if config.should_retain(iteration)
    ]

    assert retained == [6, 9, 12, 15]
    assert config.retained_sample_count() == len(retained)
