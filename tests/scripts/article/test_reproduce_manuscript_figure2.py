# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Focused checks for the dedicated manuscript Figure 2 launcher."""

import numpy as np
import pandas as pd

from scripts.article.reproduce_manuscript_figure2 import (
    Figure2Config,
    _surface_from_grid,
    build_target,
)


def test_figure2_target_uses_mu_as_scale_and_shift_as_location():
    target = build_target(Figure2Config())

    assert target.p == {"mu": 10.0, "shift": 30.0}
    values = target.pdf(np.array([29.0, 30.0, 40.0]))
    np.testing.assert_allclose(
        values,
        [0.0, 0.1, 0.1 * np.exp(-1.0)],
    )


def test_figure2_surface_has_shift_rows_and_mu_columns():
    grid = pd.DataFrame(
        {
            "mu": [20.0, 10.0, 20.0, 10.0],
            "shift": [40.0, 30.0, 30.0, 40.0],
            "rms_normalized_data_misfit": [24.0, 13.0, 23.0, 14.0],
        }
    )

    surface = _surface_from_grid(grid)

    assert surface.index.tolist() == [30.0, 40.0]
    assert surface.columns.tolist() == [10.0, 20.0]
    np.testing.assert_allclose(surface.to_numpy(), [[13.0, 23.0], [14.0, 24.0]])
