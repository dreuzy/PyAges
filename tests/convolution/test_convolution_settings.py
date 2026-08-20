"""Contracts for tracer-grid settings and cache invalidation."""

import numpy as np
import pytest

from pyage.convolution.convolution import Convolution
from pyage.convolution.settings import TracerGridSettings
from pyage.tracer.tracer_protocol import ConstantTracer


class _IncompleteTracer:
    """Object intentionally missing the convolution-grid tracer contract."""

    name = "incomplete"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("absolute_tolerance_factor", -1.0),
        ("relative_tolerance", np.nan),
        ("linear_curvature_factor", np.inf),
        ("floating_weight_epsilon_factor", -1.0),
        ("max_subdivisions", -1),
        ("max_subdivisions", 1.5),
        ("max_bins", 0),
    ],
)
def test_invalid_grid_settings_are_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        TracerGridSettings(**{field: value})


def test_observation_date_change_invalidates_grid_and_diagnostics():
    convolution = Convolution(
        ConstantTracer(concentration=1.0, datemin=1900.0),
        date=2010.0,
    )
    grid = convolution.prepare()

    assert grid.date == 2010.0
    assert convolution.prepared_grid is grid

    convolution.date = 2011.0

    assert convolution.prepared_grid is None
    assert convolution.diagnostics is None


def test_incomplete_tracer_contract_is_rejected_at_construction():
    with pytest.raises(TypeError, match="complete TracerProtocol"):
        Convolution(_IncompleteTracer(), date=2010.0)
