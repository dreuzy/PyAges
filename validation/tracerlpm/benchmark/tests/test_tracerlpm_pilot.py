import pytest

from validation.tracerlpm.benchmark.scripts.compare_tracerlpm_pilot import (
    sample_decimal_year,
)


def test_sample_date_uses_actual_leap_year_length():
    assert sample_decimal_year("PSW-1-17/08/2004") == pytest.approx(2004 + 229 / 366)
