"""Public calibration import contracts."""

import subprocess
import sys


def test_public_api_loads_the_scientific_problem_only_on_access() -> None:
    script = """
import sys
import pyage.calibration as calibration

assert "pyage.calibration.problem" not in sys.modules
assert calibration.CalibrationProblem.__name__ == "CalibrationProblem"
assert "pyage.calibration.problem" in sys.modules
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
