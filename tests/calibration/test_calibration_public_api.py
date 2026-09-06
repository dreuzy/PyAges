# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public calibration import contracts."""

import subprocess
import sys


def test_public_api_exposes_the_scientific_problem_explicitly() -> None:
    script = """
import sys
import pyages.calibration as calibration

assert calibration.__all__ == ["CalibrationProblem"]
assert calibration.CalibrationProblem.__name__ == "CalibrationProblem"
assert "pyages.calibration.problem" in sys.modules
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
