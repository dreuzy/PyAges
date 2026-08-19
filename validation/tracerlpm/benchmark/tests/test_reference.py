import csv
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

from validation.tracerlpm.benchmark.scripts.reference import cdf, moments, pdf


@pytest.mark.parametrize(
    "model,parameters,expected_mean,expected_std",
    [
        ("PFM", {"tau": 20}, 20, 0),
        ("EMM", {"tau": 20}, 20, 20),
        ("EPM", {"tau": 40, "eta": 3}, 40, 40 / 3),
        ("DM", {"tau": 40, "DP": 0.2}, 40, 40 * np.sqrt(0.4)),
    ],
)
def test_analytical_moments(model, parameters, expected_mean, expected_std):
    mean, std = moments(model, parameters)
    assert mean == pytest.approx(expected_mean)
    assert std == pytest.approx(expected_std)


@pytest.mark.parametrize(
    "model,parameters",
    [
        ("EMM", {"tau": 20}),
        ("EPM", {"tau": 40, "eta": 3}),
        ("DM", {"tau": 40, "DP": 0.2}),
    ],
)
def test_continuous_reference_is_normalized(model, parameters):
    mass = quad(
        lambda age: float(pdf(model, age, parameters)), 0, np.inf, epsabs=1e-10
    )[0]
    assert mass == pytest.approx(1.0, abs=1e-8)
    assert float(cdf(model, 1e6, parameters)) == pytest.approx(1.0, abs=1e-8)


def test_dm_cdf_is_monotone_and_bounded():
    ages = np.geomspace(1e-4, 1e4, 1000)
    values = cdf("DM", ages, {"tau": 40, "DP": 1})
    assert np.all(np.diff(values) >= -1e-14)
    assert np.all((values >= 0) & (values <= 1))


def test_generated_constant_cases_equal_covered_mass_times_input():
    path = Path(__file__).parents[1] / "references" / "forward_reference.csv"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["input"] == "constant"]
    assert len(rows) == 54
    for row in rows:
        assert float(row["concentration"]) == pytest.approx(
            100 * float(row["covered_mass"]), abs=1e-8
        )
