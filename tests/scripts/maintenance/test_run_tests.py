# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import sys

import pytest

import run_tests


@pytest.mark.parametrize(
    ("modes", "expected"),
    [
        (["extensive"], ["-q", "tests", "--run-extensive"]),
        (
            ["coverage"],
            [
                "-q",
                "tests",
                "--cov=pyages",
                "--cov-branch",
                "--cov-report=term-missing",
                "--cov-report=xml",
                "--cov-fail-under=75",
            ],
        ),
        (["validation"], ["-q", run_tests.TRACERLPM_TESTS]),
        (["collect"], ["--collect-only", "-q", "tests"]),
        (["standard", "detail"], ["-vv", "tests"]),
        (["standard", "update"], ["-q", "tests", "-s", "--update-golden"]),
    ],
)
def test_documented_scopes(modes, expected):
    command = run_tests.build_pytest_command(modes)
    assert command[:3] == [sys.executable, "-m", "pytest"]
    assert command[3:] == expected


@pytest.mark.parametrize(
    "modes",
    [
        [],
        ["detail"],
        ["update"],
        ["standard", "coverage"],
        ["validation", "update"],
        ["unknown"],
    ],
)
def test_invalid_mode_combinations_are_rejected(modes):
    with pytest.raises(ValueError):
        run_tests.build_pytest_command(modes)
