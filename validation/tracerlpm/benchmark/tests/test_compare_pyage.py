import csv
from pathlib import Path

import pytest

from pyage.convolution.settings import TracerGridSettings
from validation.tracerlpm.benchmark.scripts.compare_pyage import (
    parse_parameters,
    pyage_parameters,
    symmetric_relative_difference,
)


def test_parameter_parser_and_dm_mapping():
    parameters = parse_parameters("tau=40;DP=0.2")
    assert pyage_parameters("DM", parameters) == pytest.approx(
        {"mu": 40, "sigma": 40 * (0.4**0.5)}
    )


def test_symmetric_relative_difference_is_signed_and_bounded():
    assert symmetric_relative_difference(10, 10) == 0
    assert symmetric_relative_difference(11, 10) > 0
    assert symmetric_relative_difference(9, 10) < 0
    assert abs(symmetric_relative_difference(1, 0)) <= 2


def test_reference_contains_expected_number_of_cases():
    path = Path(__file__).parents[1] / "references" / "forward_reference.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 270


def test_invalid_grid_settings_are_rejected():
    with pytest.raises(ValueError, match="relative_tolerance"):
        TracerGridSettings(relative_tolerance=-1.0)
