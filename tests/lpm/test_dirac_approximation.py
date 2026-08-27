# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Unit tests for the private PDF approximations used by Dirac models."""

import numpy as np
import pytest

from pyages.lpm.models._dirac_approximation import (
    build_normalized_linear_pdf,
    build_regularized_dirac_pdf,
    rectangular_dirac_approximation,
)
from pyages.lpm.models.dirac import DiracLpm
from tests.utils import paths as test_paths


def test_linear_pdf_uses_its_exact_piecewise_linear_area() -> None:
    grid = np.array([0.0, 1.0, 3.0])
    density = np.array([0.0, 2.0, 0.0])

    pdf = build_normalized_linear_pdf(grid, density)

    assert np.trapezoid(pdf(grid), grid) == pytest.approx(1.0)
    assert pdf(np.array([-1.0, 4.0])) == pytest.approx([0.0, 0.0])


def test_zero_density_builds_a_zero_extended_interpolator() -> None:
    grid = np.array([0.0, 1.0, 2.0])

    pdf = build_normalized_linear_pdf(grid, np.zeros_like(grid))

    assert pdf(np.array([-1.0, 0.5, 3.0])) == pytest.approx([0.0, 0.0, 0.0])


@pytest.mark.parametrize(
    ("grid", "density", "message"),
    [
        ([0.0], [1.0], "at least 2"),
        ([0.0, 1.0], [1.0], "match grid's shape"),
        ([0.0, 0.0], [1.0, 1.0], "strictly increasing"),
        ([0.0, np.inf], [1.0, 1.0], "grid values must be finite"),
        ([0.0, 1.0], [1.0, np.nan], "density values must be finite"),
        ([0.0, 1.0], [1.0, -1.0], "density values must be non-negative"),
    ],
)
def test_linear_pdf_rejects_invalid_samples(grid, density, message) -> None:
    with pytest.raises(ValueError, match=message):
        build_normalized_linear_pdf(grid, density)


def test_rectangular_approximation_has_explicit_closed_support() -> None:
    times = np.array([0.49, 0.5, 1.0, 1.5, 1.51])

    values = rectangular_dirac_approximation(times, center=1.0, width=1.0)

    assert values == pytest.approx([0.0, 1.0, 1.0, 1.0, 0.0])


@pytest.mark.parametrize("width", [0.0, -1.0, np.inf, np.nan])
def test_rectangular_approximation_requires_positive_finite_width(width) -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        rectangular_dirac_approximation([0.0, 1.0], width=width)


def test_regularized_dirac_pdf_combines_and_normalizes_multiple_masses() -> None:
    grid = np.linspace(0.0, 4.0, 9)

    pdf = build_regularized_dirac_pdf(
        grid,
        centers=[1.0, 3.0],
        weights=[0.25, 0.75],
        width=0.5,
    )

    assert np.trapezoid(pdf(grid), grid) == pytest.approx(1.0)
    assert pdf(3.0) == pytest.approx(3.0 * pdf(1.0))
    assert pdf(np.array([-1.0, 5.0])) == pytest.approx([0.0, 0.0])


@pytest.mark.parametrize(
    ("centers", "weights", "message"),
    [
        ([], [], "non-empty"),
        ([1.0, 2.0], [1.0], "match centers"),
        ([1.0], [-1.0], "non-negative"),
        ([1.0], [0.0], "positive total mass"),
    ],
)
def test_regularized_dirac_pdf_validates_mass_definition(
    centers, weights, message
) -> None:
    with pytest.raises(ValueError, match=message):
        build_regularized_dirac_pdf(
            [0.0, 1.0, 2.0],
            centers=centers,
            weights=weights,
            width=1.0,
        )


def test_dirac_pdf_is_normalized_at_zero_age_and_zero_outside_its_grid() -> None:
    model = DiracLpm(mu=0.0, directory_lpm=str(test_paths.lpm_data_dir()))
    grid = np.linspace(0.0, 120.0, 201)

    values = model.pdf(grid)

    assert np.trapezoid(values, grid) == pytest.approx(1.0)
    assert model.pdf(np.array([-1.0, 121.0])) == pytest.approx([0.0, 0.0])
