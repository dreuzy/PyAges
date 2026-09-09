# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for the dedicated calibration-target signature module."""

import pyages.calibration.problem as problem_module
from pyages.calibration.target_signature import (
    CALIBRATION_TARGET_SIGNATURE_VERSION,
    CalibrationTargetSignature,
    LpmParameterTargetSignature,
    LpmTargetSignature,
    ObservationTargetSignature,
    TracerGridArraySignature,
    TracerGridTargetSignature,
    build_calibration_target_signature,
)
from tests.calibration.test_calibration_problem import _prepared_problem


def test_target_signature_records_are_owned_by_the_dedicated_module() -> None:
    records = (
        CalibrationTargetSignature,
        LpmParameterTargetSignature,
        LpmTargetSignature,
        ObservationTargetSignature,
        TracerGridArraySignature,
        TracerGridTargetSignature,
    )

    assert all(
        record.__module__ == "pyages.calibration.target_signature" for record in records
    )


def test_problem_module_has_no_signature_compatibility_aliases() -> None:
    assert not hasattr(problem_module, "CalibrationTargetSignature")
    assert not hasattr(problem_module, "CALIBRATION_TARGET_SIGNATURE_VERSION")


def test_dedicated_builder_matches_the_problem_contract(tmp_path) -> None:
    problem = _prepared_problem(tmp_path)

    signature = build_calibration_target_signature(
        problem.lpm,
        problem.observations,
        problem.tracers,
    )

    assert signature == problem.target_signature()
    assert signature.version == CALIBRATION_TARGET_SIGNATURE_VERSION
    assert len(signature.sha256) == 64
