# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Input-boundary tests for the synthetic recovery qualification experiment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyages import qualification
from pyages.config.runtime import DisplayOptions


def _display(tmp_path) -> DisplayOptions:
    display = DisplayOptions()
    display.directory = tmp_path
    return display


def test_synthetic_recovery_requires_a_calibration_strategy() -> None:
    with pytest.raises(ValueError, match="calib_strategy"):
        qualification.SyntheticRecoveryExperiment()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"ncase": 0}, "ncase"),
        ({"sample_count": 0}, "sample_count"),
        ({"error": -0.1}, "error"),
        ({"lpm_type": ""}, "lpm_type"),
        ({"tracer_names": []}, "tracer_names"),
    ],
)
def test_synthetic_recovery_rejects_invalid_experiment_controls(
    tmp_path, overrides, message
) -> None:
    arguments = {
        "calib_strategy": SimpleNamespace(method="test"),
        "display_options": _display(tmp_path),
    }
    arguments.update(overrides)

    with pytest.raises(ValueError, match=message):
        qualification.SyntheticRecoveryExperiment(**arguments)


def test_synthetic_recovery_requires_an_output_directory() -> None:
    with pytest.raises(ValueError, match="display_options.directory"):
        qualification.SyntheticRecoveryExperiment(
            calib_strategy=SimpleNamespace(method="test")
        )


def test_supplied_synthetic_target_must_match_the_configured_model(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        qualification,
        "ConvolutionTracers",
        lambda **_kwargs: SimpleNamespace(),
    )
    experiment = qualification.SyntheticRecoveryExperiment(
        calib_strategy=SimpleNamespace(method="test"),
        lpm_type="exp",
        display_options=_display(tmp_path),
    )

    with pytest.raises(ValueError, match="does not match"):
        experiment.perform_one_case(
            0,
            lpm_random=False,
            lpm_target=SimpleNamespace(name="ig"),
        )


def test_non_random_synthetic_case_requires_a_target(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        qualification,
        "ConvolutionTracers",
        lambda **_kwargs: SimpleNamespace(),
    )
    experiment = qualification.SyntheticRecoveryExperiment(
        calib_strategy=SimpleNamespace(method="test"),
        display_options=_display(tmp_path),
    )

    with pytest.raises(ValueError, match="lpm_target is required"):
        experiment.perform_one_case(0, lpm_random=False)
