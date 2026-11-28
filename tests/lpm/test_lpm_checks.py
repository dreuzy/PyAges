# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Fast checker contracts for continuous, discrete, and unknown LPMs."""

from pyages.lpm.checks import check_lpm


def test_continuous_lpm_check_exercises_affine_convolution() -> None:
    report = check_lpm("exp")

    assert not report.failed
    assert report.warnings == 0
    assert any(
        finding.check == "constant-and-affine-convolution"
        and finding.level == "OK"
        for finding in report.findings
    )


def test_discrete_lpm_check_marks_continuous_probe_not_applicable() -> None:
    report = check_lpm("dirac")

    assert not report.failed
    assert report.warnings == 1


def test_unknown_lpm_check_returns_a_failed_construction_report() -> None:
    report = check_lpm("not_installed")

    assert report.failed
    assert report.findings[0].check == "construction"
