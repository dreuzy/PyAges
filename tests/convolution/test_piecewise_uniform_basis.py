# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Equivalence and cache contracts for piecewise-uniform convolution."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pyages.convolution.convolution as convolution_module
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.convolution import Convolution, ConvolutionError
from pyages.convolution._piecewise_uniform import prepare_piecewise_uniform_basis
from pyages.convolution.continuous_integration import convolve_prepared_grid
from pyages.lpm import build_lpm
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.tracer.simple_tracers import ConstantTracer, SyntheticTracer
from tests.utils import paths as test_paths

ROOT = Path(__file__).resolve().parents[2]
ALBUQUERQUE = ROOT / "examples" / "natural" / "albuquerque"


def _shape_free_lpm():
    model = build_lpm(
        "shapefree_n_oldbin",
        directory_lpm=str(test_paths.lpm_data_dir()),
    )
    model.set_param_from_array([0.0, 0.0, 0.0])
    return model


def test_albuquerque_cached_basis_matches_continuous_reference() -> None:
    """Compare the optimized path with the previous production integration."""
    observations = Concentrations.from_file(ALBUQUERQUE / "data" / "SSW_2007.txt")
    problem = CalibrationProblem(
        observations,
        "shapefree_n_oldbin",
        lpm_directory=ALBUQUERQUE / "data_lpm",
    ).prepare()
    assert problem.lpm is not None
    assert problem.tracers is not None

    fixed_states = np.asarray(
        [
            [-8.0, -8.0, -8.0, -8.0],
            [8.0, 8.0, 8.0, 8.0],
            [-8.0, 8.0, -8.0, 8.0],
            [0.0, 0.0, 0.0, 0.0],
        ]
    )
    random_states = np.random.default_rng(20260904).uniform(-8.0, 8.0, (6, 4))
    for parameters in np.vstack((fixed_states, random_states)):
        problem.lpm.set_param_from_array(parameters)
        for convolution in problem.tracers.convolutions:
            grid = convolution.prepared_grid
            assert grid is not None
            reference, reference_diagnostics = convolve_prepared_grid(
                grid,
                problem.lpm.cdf_and_partial_first_moment,
                problem.lpm.name,
                convolution.grid_settings,
            )

            optimized = convolution.convolve(problem.lpm)

            assert optimized == pytest.approx(reference, rel=2.0e-12, abs=3.0e-12)
            assert convolution.diagnostics is not None
            assert convolution.diagnostics.window_mass == pytest.approx(
                reference_diagnostics.window_mass,
                rel=0.0,
                abs=2.0e-15,
            )
            assert convolution.diagnostics.n_bins == reference_diagnostics.n_bins
            assert convolution.diagnostics.min_weight == pytest.approx(
                reference_diagnostics.min_weight,
                rel=0.0,
                abs=2.0e-15,
            )
            assert (
                convolution.diagnostics.clipped_weight_count
                == reference_diagnostics.clipped_weight_count
            )


def test_piecewise_uniform_basis_is_built_once_until_date_changes(monkeypatch) -> None:
    """Reuse one basis across parameter proposals and invalidate it with date."""
    model = _shape_free_lpm()
    tracer = SyntheticTracer(
        datemin=1900.0,
        concentration_fn=lambda _date, age: 1.0 + 0.01 * np.asarray(age),
    )
    convolution = Convolution(tracer, date=2010.0)
    real_prepare = convolution_module.prepare_piecewise_uniform_basis
    calls: list[float] = []

    def recorded_prepare(*args, **kwargs):
        calls.append(convolution.date)
        return real_prepare(*args, **kwargs)

    monkeypatch.setattr(
        convolution_module,
        "prepare_piecewise_uniform_basis",
        recorded_prepare,
    )

    convolution.prepare(model)
    for parameters in ([0.0, 0.0, 0.0], [-4.0, 1.0, 6.0], [8.0, -8.0, 0.0]):
        model.set_param_from_array(parameters)
        assert np.isfinite(convolution.convolve(model))
    assert calls == [2010.0]

    convolution.date = 2009.0
    assert np.isfinite(convolution.convolve(model))
    assert calls == [2010.0, 2009.0]


def test_prepared_piecewise_uniform_basis_owns_read_only_arrays() -> None:
    """Prevent mutation of a cached response through caller-owned arrays."""
    grid = Convolution(
        ConstantTracer(concentration=2.0, datemin=2000.0),
        date=2010.0,
    ).prepare()
    edges = np.asarray([0.0, 2.0, 10.0])

    basis = prepare_piecewise_uniform_basis(
        grid,
        edges,
        "test_piecewise_uniform",
        Convolution(ConstantTracer(), date=2010.0).grid_settings,
    )
    edges[1] = 4.0

    assert basis.bin_edges.tolist() == [0.0, 2.0, 10.0]
    for values in (basis.bin_edges, basis.responses, basis.cdf_at_grid_edges):
        assert not values.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            values.flat[0] = 1.0


def test_piecewise_uniform_strategy_requires_explicit_model_contract() -> None:
    """Reject a strategy declaration without bin geometry and fractions."""

    class IncompletePiecewiseUniform:
        name = "incomplete_piecewise_uniform"
        convolution_strategy = ConvolutionStrategy.PIECEWISE_UNIFORM

    convolution = Convolution(ConstantTracer(), date=2010.0)

    with pytest.raises(ConvolutionError, match=r"bin_edges\(\).*fractions\(\)"):
        convolution.convolve(IncompletePiecewiseUniform())  # type: ignore[arg-type]
