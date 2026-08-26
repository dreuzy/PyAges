"""Contracts for regular parameter grids."""

import numpy as np
import pytest

from pyage.calibration.utils.parameter_grid import ParameterGrid


def test_points_keep_declared_cartesian_order() -> None:
    grid = ParameterGrid([0.0, 10.0], [2.0, 12.0], 2, ["first", "second"])

    assert grid.shape == (3, 3)
    assert grid.size == 9
    np.testing.assert_allclose(
        grid.points(),
        [
            [0.0, 10.0],
            [0.0, 11.0],
            [0.0, 12.0],
            [1.0, 10.0],
            [1.0, 11.0],
            [1.0, 12.0],
            [2.0, 10.0],
            [2.0, 11.0],
            [2.0, 12.0],
        ],
    )


def test_reshape_supports_more_than_four_dimensions() -> None:
    grid = ParameterGrid([0.0] * 5, [1.0] * 5, 1, list("abcde"))
    values = np.arange(grid.size, dtype=float)

    reshaped = grid.reshape(values)

    assert reshaped.shape == (2, 2, 2, 2, 2)
    np.testing.assert_array_equal(reshaped.ravel(), values)


@pytest.mark.parametrize(
    ("minima", "maxima", "target_size", "names", "message"),
    [
        ([], [], 1, [], "at least one"),
        ([0.0], [1.0, 2.0], 1, ["a"], "same length"),
        ([0.0], [1.0], 0, ["a"], "strictly positive"),
    ],
)
def test_invalid_grid_definition_is_rejected(
    minima, maxima, target_size, names, message
) -> None:
    with pytest.raises(ValueError, match=message):
        ParameterGrid(minima, maxima, target_size, names)


def test_reshape_rejects_wrong_value_count() -> None:
    grid = ParameterGrid([0.0], [1.0], 1, ["a"])

    with pytest.raises(ValueError, match="Expected 2 grid values"):
        grid.reshape([1.0])
