# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public calibration import contracts."""

import subprocess
import sys


def test_public_api_exposes_problem_objectives_and_deterministic_inversion() -> None:
    script = """
import sys
import pyages.calibration as calibration

assert calibration.__all__ == [
    "CalibrationProblem",
    "InversionAttempt",
    "InversionResult",
    "ObjectiveSpec",
    "ResidualRecord",
    "invert_lpm",
]
assert calibration.CalibrationProblem.__name__ == "CalibrationProblem"
assert calibration.ObjectiveSpec.__name__ == "ObjectiveSpec"
assert callable(calibration.invert_lpm)
assert "pyages.calibration.problem" in sys.modules
assert "pyages.calibration.inversion" in sys.modules
assert not hasattr(calibration, "_EXPORTS")
assert "__getattr__" not in calibration.__dict__
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
