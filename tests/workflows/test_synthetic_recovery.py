# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Input-boundary tests for the synthetic recovery qualification workflow."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyages.config.runtime import DisplayOptions
from pyages.workflows import synthetic_recovery


def _display(tmp_path) -> DisplayOptions:
    display = DisplayOptions()
    display.directory = tmp_path
    return display


def test_synthetic_recovery_requires_a_calibration_strategy() -> None:
    with pytest.raises(ValueError, match="calib_strategy"):
        synthetic_recovery.SyntheticRecoveryWorkflow()


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
        synthetic_recovery.SyntheticRecoveryWorkflow(**arguments)


def test_synthetic_recovery_requires_an_output_directory() -> None:
    with pytest.raises(ValueError, match="display_options.directory"):
        synthetic_recovery.SyntheticRecoveryWorkflow(
            calib_strategy=SimpleNamespace(method="test")
        )


def test_supplied_synthetic_target_must_match_the_configured_model(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        synthetic_recovery,
        "ConvolutionTracers",
        lambda **_kwargs: SimpleNamespace(),
    )
    workflow = synthetic_recovery.SyntheticRecoveryWorkflow(
        calib_strategy=SimpleNamespace(method="test"),
        lpm_type="exp",
        display_options=_display(tmp_path),
    )

    with pytest.raises(ValueError, match="does not match"):
        workflow.perform_one_case(
            0,
            lpm_random=False,
            lpm_target=SimpleNamespace(name="ig"),
        )


def test_non_random_synthetic_case_requires_a_target(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        synthetic_recovery,
        "ConvolutionTracers",
        lambda **_kwargs: SimpleNamespace(),
    )
    workflow = synthetic_recovery.SyntheticRecoveryWorkflow(
        calib_strategy=SimpleNamespace(method="test"),
        display_options=_display(tmp_path),
    )

    with pytest.raises(ValueError, match="lpm_target is required"):
        workflow.perform_one_case(0, lpm_random=False)
