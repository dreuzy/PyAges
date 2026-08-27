# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Tests for shared figure helpers."""

import matplotlib as mpl
import numpy as np

from pyages.tools.figures_additional import cmap_white_jet


def test_cmap_white_jet_infers_size_from_its_colors(monkeypatch) -> None:
    """Build the colormap without Matplotlib's deprecated ``N`` argument."""
    listed_colormap = mpl.colors.ListedColormap
    captured = {}

    def listed_colormap_without_n(colors, name="from_list"):
        captured["colors"] = np.asarray(colors)
        return listed_colormap(colors, name=name)

    monkeypatch.setattr(mpl.colors, "ListedColormap", listed_colormap_without_n)

    cmap = cmap_white_jet()

    assert cmap.name == "myColorMap"
    assert cmap.N == 320
    assert captured["colors"].shape == (320, 4)
    np.testing.assert_allclose(captured["colors"][0], np.ones(4))
