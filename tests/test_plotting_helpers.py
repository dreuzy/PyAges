# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Behavioral contracts for shared plotting primitives."""

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt

import pyages._plotting as plotting


def test_white_low_colormap_uses_perceptual_default_and_white_floor() -> None:
    colormap = plotting.white_low_colormap()

    assert colormap.name == "pyages_white_cividis"
    assert colormap.N == 320
    np.testing.assert_allclose(colormap.colors[0], np.ones(4))


def test_white_low_colormap_preserves_explicit_legacy_choice() -> None:
    colormap = plotting.white_low_colormap(base="jet")
    legacy_colors = matplotlib.colormaps["jet"](np.arange(256))

    assert colormap.name == "pyages_white_jet"
    assert colormap.N == 320
    np.testing.assert_allclose(colormap.colors[64:], legacy_colors)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"fade_samples": 0}, "must be positive"),
        ({"base": "not-a-colormap"}, "Unknown Matplotlib colormap"),
    ],
)
def test_white_low_colormap_rejects_invalid_configuration(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        plotting.white_low_colormap(**kwargs)


def test_create_figure_applies_labels_and_style() -> None:
    figure, axis = plotting.create_figure(
        x_label="age",
        y_label="density",
        title="Distribution",
    )

    assert axis.get_xlabel() == "age"
    assert axis.get_ylabel() == "density"
    assert axis.get_title() == "Distribution"
    assert any(line.get_visible() for line in axis.get_xgridlines())
    plt.close(figure)


def test_finalize_figure_creates_parent_adds_suffix_and_closes(tmp_path) -> None:
    figure, _ = plt.subplots()

    output = plotting.finalize_figure(figure, tmp_path / "nested" / "diagnostic")

    assert output == tmp_path / "nested" / "diagnostic.png"
    assert output.is_file()
    assert not plt.fignum_exists(figure.number)


def test_finalize_figure_preserves_numeric_name_suffix(tmp_path) -> None:
    figure, _ = plt.subplots()

    output = plotting.finalize_figure(figure, tmp_path / "reachable_0.0")

    assert output == tmp_path / "reachable_0.0.png"
    assert output.is_file()


def test_histogram_scatter_filters_nonfinite_pairs_and_builds_legend() -> None:
    figure, axis = plotting.plot_histogram_scatter(
        histogram_x=[0.0, 1.0, np.nan],
        histogram_y=[1.0, 2.0, 3.0],
        histogram_label="comparison",
        scatter_x=[0.0, np.inf, 2.0],
        scatter_y=[2.0, 3.0, 4.0],
        scatter_label="samples",
        reference_x=1.0,
        reference_y=3.0,
        reference_label="reference",
    )

    assert [text.get_text() for text in axis.get_legend().get_texts()] == [
        "comparison",
        "samples",
        "reference",
    ]
    assert len(axis.collections[1].get_offsets()) == 2
    assert np.isfinite(axis.get_xlim()).all()
    assert np.isfinite(axis.get_ylim()).all()
    plt.close(figure)


def test_histogram_scatter_accepts_empty_layers() -> None:
    figure, axis = plotting.plot_histogram_scatter(
        histogram_x=[],
        histogram_y=[],
        scatter_x=[np.nan],
        scatter_y=[np.inf],
    )

    assert axis.get_legend() is None
    assert len(axis.collections) == 0
    plt.close(figure)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"scatter_x": [1.0]},
        {"histogram_x": [1.0], "histogram_y": [1.0, 2.0]},
        {"reference_x": 1.0},
    ],
)
def test_histogram_scatter_rejects_incomplete_pairs(kwargs) -> None:
    with pytest.raises(ValueError, match="provided together|same length"):
        plotting.plot_histogram_scatter(**kwargs)
