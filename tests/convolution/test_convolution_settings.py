# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for tracer-grid settings and cache invalidation."""

import numpy as np
import pytest

from pyages.convolution import Convolution, PreparedTracerGrid, TracerGridSettings
from pyages.tracer.protocols import ConvolutionTracerProtocol, TracerProtocol
from pyages.tracer.tracer_protocol import ConstantTracer


class _IncompleteTracer:
    """Object intentionally missing the convolution-grid tracer contract."""

    name = "incomplete"


class _MinimalConvolutionTracer:
    """Tracer implementing only the numerical convolution contract."""

    name = "minimal"
    datemin = 1900.0
    datemax = 2100.0
    convolution_dates = None
    convolution_initial_bins = 1

    @staticmethod
    def get_concentration(date, time):
        if np.isscalar(time):
            return 1.0
        return np.ones_like(time, dtype=float)


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
    with pytest.raises(TypeError, match="ConvolutionTracerProtocol"):
        Convolution(_IncompleteTracer(), date=2010.0)


def test_minimal_convolution_tracer_is_accepted_without_summary_methods():
    tracer = _MinimalConvolutionTracer()

    assert isinstance(tracer, ConvolutionTracerProtocol)
    assert not isinstance(tracer, TracerProtocol)

    convolution = Convolution(tracer, date=2010.0)
    grid = convolution.prepare()

    assert convolution.tracer is tracer
    assert grid.edges.tolist() == [0.0, 110.0]


@pytest.mark.parametrize(
    "date",
    [np.nan, np.inf, -np.inf, True, "2010", np.array([2010.0])],
)
def test_invalid_observation_date_is_rejected_at_construction(date):
    with pytest.raises(ValueError, match="observation date"):
        Convolution(ConstantTracer(datemin=1900.0), date=date)


def test_observation_date_before_tracer_history_is_rejected_atomically():
    convolution = Convolution(ConstantTracer(datemin=1900.0), date=2010.0)

    with pytest.raises(ValueError, match="must be >= tracer.datemin"):
        convolution.date = 1899.0

    assert convolution.date == 2010.0


def test_prepared_grid_arrays_are_read_only():
    grid = Convolution(ConstantTracer(datemin=2000.0), date=2010.0).prepare()

    for values in (grid.edges, grid.k_left, grid.k_mid, grid.k_right):
        assert not values.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            values[...] = 0.0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"date": np.nan}, "date must be finite"),
        (
            {
                "edges": np.array([0.0, np.nan]),
                "k_left": np.array([1.0]),
                "k_mid": np.array([1.0]),
                "k_right": np.array([1.0]),
            },
            "edges must be a finite vector",
        ),
        ({"edges": np.array([])}, "edges must contain at least one value"),
        (
            {
                "edges": np.array([0.0, 0.0]),
                "k_left": np.array([1.0]),
                "k_mid": np.array([1.0]),
                "k_right": np.array([1.0]),
            },
            "edges must be strictly increasing",
        ),
        ({"k_left": np.array([])}, "k_left must contain 1 values"),
    ],
)
def test_prepared_grid_rejects_invalid_topology(overrides, message):
    values = {
        "date": 2010.0,
        "edges": np.array([0.0, 1.0]),
        "k_left": np.array([1.0]),
        "k_mid": np.array([1.0]),
        "k_right": np.array([1.0]),
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        PreparedTracerGrid(**values)
