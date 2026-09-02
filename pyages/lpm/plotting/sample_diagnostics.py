# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file creates diagnostic figures from an LPM calibration sample table.

"""Inspect parameter and concentration samples produced by LPM calibration.

Parameter histograms describe marginal uncertainty, objective-versus-parameter
plots locate good and poor fits, and cyclic pair plots reveal dependencies
without constructing a full pair matrix. Optional reference values and a second
sample table make independent solutions or calibration methods directly visible.

The module can also overlay configured prior shapes and compare pairs of modeled
tracer concentrations with observations. It is a visualization layer only:
non-finite values are omitted from figures, but the underlying sample table and
its calibration results are not altered.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np

import pyages._plotting as plotting

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from pyages.lpm.samples.table import LpmSampleTable


def _output_path(directory: str | Path | None, filename: str) -> str | None:
    """Return a path inside ``directory``, or ``None`` when saving is disabled."""

    return None if directory is None else str(Path(directory) / filename)


def plot_parameter_pair(
    distribution: "LpmSampleTable",
    keyx: str,
    keyy: str,
    *,
    axis: "Axes | None" = None,
) -> None:
    """Plot samples of one stored parameter against another.

    This lightweight entry point is used when the caller already owns the
    Matplotlib axis.  It shows the sampled cloud without creating or saving a
    complete diagnostic figure.
    """
    frame = distribution.frame
    target = plt.gca() if axis is None else axis
    target.scatter(
        frame[keyx],
        frame[keyy],
        marker="+",
        c="red",
        s=10,
        label="model",
    )


def plot_parameter_diagnostics(
    distribution: "LpmSampleTable",
    self_method: str = "",
    lpm_reference: Any = None,
    lpm_2nd: "LpmSampleTable | None" = None,
    lpm_2nd_method: str = "",
    directory: str | Path | None = None,
    display_text: bool = False,
) -> None:
    """Create a compact set of diagnostics for calibrated parameters.

    For each parameter, the function shows its sampled distribution and how
    the objective value changes across that distribution.  It also plots each
    parameter against the next one, closing the cycle at the last parameter,
    to expose common dependencies without producing every possible pair.

    Reference values and a second distribution can be added for comparison.
    Figures are saved only when ``directory`` is provided.
    """
    names = distribution.get_param_names()
    if display_text:
        print("DISTRIBUTION OF PARAMETERS")
    # Marginal histograms reveal uncertainty or multimodality in each
    # parameter independently of the others.
    for name in names:
        _plot_param_histogram(
            distribution,
            name,
            self_method,
            lpm_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
        )

    if display_text:
        print("OBJECTIVE FUNCTION")
    # These plots show whether good fits occupy a narrow or poorly constrained
    # part of each sampled parameter range.
    for name in names:
        _plot_obj_vs_param(
            distribution,
            name,
            self_method,
            lpm_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
        )

    if display_text:
        print("PARAMETERS")
    # Pair consecutive parameters and close the cycle.  This keeps the number
    # of figures manageable while still including every parameter.
    if len(names) >= 2:
        for index in range(len(names)):
            _plot_param_pair(
                distribution,
                names,
                index,
                self_method,
                lpm_reference,
                lpm_2nd,
                lpm_2nd_method,
                directory,
            )


def plot_prior_comparison(
    distribution: "LpmSampleTable",
    lpm_reference: Any = None,
    lpm_2nd: "LpmSampleTable | None" = None,
    lpm_2nd_method: str = "",
    directory: str | Path | None = None,
    display_text: bool = False,
    prior: Any = None,
) -> None:
    """Compare sampled parameter distributions with their configured priors.

    The prior curve is rescaled to the height of the sample histogram so the
    figure compares shapes rather than probability normalizations.  This makes
    it easier to see which parts of a prior were retained or ruled out by the
    calibration data.
    """
    if display_text:
        print("DISTRIBUTION OF PARAMETERS")
    for name in distribution.get_param_names():
        _plot_param_histogram_apriori(
            distribution,
            name,
            lpm_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
            prior,
        )


def plot_concentration_diagnostics(
    distribution: "LpmSampleTable",
    self_method: str = "",
    concentrations_reference: Any = None,
    lpm_2nd: "LpmSampleTable | None" = None,
    lpm_2nd_method: str = "",
    directory: str | Path | None = None,
) -> None:
    """Plot pairwise diagnostics for concentrations predicted by the samples.

    Consecutive tracers are paired and the last tracer is paired with the
    first.  The resulting clouds show prediction correlations; optional
    observations and a second sample table provide direct comparisons.
    """
    names = distribution.get_concentration_names()
    for index in range(len(names)):
        _plot_concentration_pair(
            distribution,
            index,
            (index + 1) % len(names),
            self_method,
            concentrations_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
        )


def _finite_parameter_values(distribution: "LpmSampleTable", name: str) -> np.ndarray:
    """Return finite samples for one parameter, excluding unplottable values."""

    values = np.asarray(distribution.frame[name].tolist(), dtype=float)
    return values[np.isfinite(values)]


def _parameter_bins(
    distribution: "LpmSampleTable", name: str, values: np.ndarray
) -> np.ndarray:
    """Build histogram edges from the model range and the sampled values.

    The nominal model range supplies a common bin width, which makes figures
    from different calibration methods visually comparable.  An empty array
    signals that the requested histogram cannot be drawn safely.
    """

    model = distribution.lpm_template
    binwidth = model.get_calibration_range_width(name) / 100
    if not np.isfinite(binwidth) or binwidth <= 0:
        return np.array([])
    return np.arange(
        min(max(values) / 2, model.get_calibration_range(name)[0]),
        model.get_calibration_range(name)[1] + binwidth,
        binwidth,
    )


def _plot_param_histogram(
    distribution: "LpmSampleTable",
    name: str,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmSampleTable | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    """Plot one parameter histogram with optional comparison information.

    Non-finite samples or unusable calibration ranges cause the figure to be
    skipped instead of sending invalid histogram data to Matplotlib.
    """

    values = _finite_parameter_values(distribution, name)
    if values.size == 0:
        return
    model = distribution.lpm_template
    bins = _parameter_bins(distribution, name, values)
    if bins.size < 2:
        return
    figure, axis = plotting.create_figure(
        x_label=name,
        y_label="Count",
        title=model.name,
    )
    axis.hist(values, density=True, bins=bins, histtype="barstacked", label=self_method)
    if lpm_reference is not None:
        axis.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        values_2nd = _finite_parameter_values(lpm_2nd, name)
        if values_2nd.size > 0:
            axis.hist(
                values_2nd,
                density=True,
                bins=bins,
                histtype="barstacked",
                label=lpm_2nd_method,
            )
    axis.set_xlim(*model.get_calibration_range(name))
    axis.legend()
    output = _output_path(directory, f"comp_{name}")
    if output is not None:
        plotting.finalize_figure(figure, output)


def _plot_obj_vs_param(
    distribution: "LpmSampleTable",
    name: str,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmSampleTable | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    """Plot the calibration objective against one sampled parameter.

    This view treats the stored objective as a goodness-of-fit diagnostic.  It
    shows where solutions lie along the parameter axis, without interpreting
    the objective itself as a probability density.
    """

    model = distribution.lpm_template
    frame = distribution.frame
    figure, axis = plotting.create_figure(
        x_label=name,
        y_label="obj_function",
        title=model.name,
    )
    axis.scatter(
        frame[name].tolist(),
        frame["obj_function"].tolist(),
        marker="x",
        c="blue",
        s=10,
        label=self_method,
    )
    if lpm_reference is not None:
        axis.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        other = lpm_2nd.frame
        axis.scatter(
            other[name],
            other["obj_function"],
            marker="+",
            c="red",
            s=10,
            label=lpm_2nd_method,
        )
    axis.legend()
    output = _output_path(directory, f"objfunction_{name}")
    if output is not None:
        plotting.finalize_figure(figure, output)


def _plot_param_pair(
    distribution: "LpmSampleTable",
    names: list[str],
    index: int,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmSampleTable | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    """Plot one parameter against its cyclic neighbour in the model order.

    Cycling from the last parameter back to the first gives one overview plot
    per parameter without constructing the full quadratic pair matrix.
    """

    index_next = (index + 1) % len(names)
    frame = distribution.frame
    other = None if lpm_2nd is None else lpm_2nd.frame
    scatterx = frame[names[index]].tolist() or None
    scattery = frame[names[index_next]].tolist() if scatterx is not None else None
    refx = None if lpm_reference is None else lpm_reference.p[names[index]]
    refy = None if lpm_reference is None else lpm_reference.p[names[index_next]]
    plotting.plot_histogram_scatter(
        histogram_x=None if other is None else other[names[index]],
        histogram_y=None if other is None else other[names[index_next]],
        histogram_label=lpm_2nd_method,
        scatter_x=scatterx,
        scatter_y=scattery,
        scatter_label=self_method,
        reference_x=refx,
        reference_y=refy,
        reference_label="reference",
        x_label=names[index],
        y_label=names[index_next],
        title=distribution.lpm_template.name,
        filename=_output_path(
            directory,
            f"comp2D_{names[index]}_{names[index_next]}",
        ),
    )


def _plot_param_histogram_apriori(
    distribution: "LpmSampleTable",
    name: str,
    lpm_reference: Any,
    lpm_2nd: "LpmSampleTable | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
    prior: Any,
) -> None:
    """Overlay a sampled parameter histogram and its configured prior shape."""

    values = _finite_parameter_values(distribution, name)
    if values.size == 0:
        return
    model = distribution.lpm_template
    bins = _parameter_bins(distribution, name, values)
    if bins.size < 2:
        return
    figure, axis = plotting.create_figure(
        x_label=name,
        y_label="Count",
        title=model.name,
    )
    histogram = axis.hist(
        values, density=True, bins=bins, histtype="barstacked", label="MH"
    )
    nonzero_hist = histogram[0][histogram[0] != 0]
    prior_density = prior.parameters[name]
    nonzero_prior = prior_density[prior_density[:, 1] != 0, 1]
    # The histogram contains sample counts whereas the prior is a density.
    # Aligning their typical non-zero heights is only a visual comparison; the
    # resulting scale is not a posterior-to-prior probability ratio.
    rescaling = np.mean(nonzero_hist) / np.mean(nonzero_prior)
    axis.plot(prior_density[:, 0], prior_density[:, 1] * rescaling)
    if lpm_reference is not None:
        axis.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        values_2nd = _finite_parameter_values(lpm_2nd, name)
        if values_2nd.size > 0:
            axis.hist(
                values_2nd,
                density=True,
                bins=bins,
                histtype="barstacked",
                label=lpm_2nd_method,
            )
    axis.set_xlim(*model.get_calibration_range(name))
    axis.legend()
    output = _output_path(directory, f"comp_apriori{name}")
    if output is not None:
        plotting.finalize_figure(figure, output)


def _plot_concentration_pair(
    distribution: "LpmSampleTable",
    index: int,
    index_next: int,
    self_method: str,
    concentrations_reference: Any,
    lpm_2nd: "LpmSampleTable | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    """Plot predicted concentrations for one tracer and its cyclic neighbour.

    Observed concentrations, when supplied, identify the target point that a
    well-fitting prediction cloud should approach.
    """

    names = distribution.get_concentration_names()
    frame = distribution.frame
    if names[index] not in frame:
        return
    other = None if lpm_2nd is None else lpm_2nd.frame
    refx = (
        None
        if concentrations_reference is None
        else concentrations_reference.frame["concentration"][index]
    )
    refy = (
        None
        if concentrations_reference is None
        else concentrations_reference.frame["concentration"][index_next]
    )
    plotting.plot_histogram_scatter(
        histogram_x=None if other is None else other[names[index]],
        histogram_y=None if other is None else other[names[index_next]],
        histogram_label=lpm_2nd_method,
        scatter_x=frame[names[index]],
        scatter_y=frame[names[index_next]],
        scatter_label=self_method,
        reference_x=refx,
        reference_y=refy,
        reference_label="reference",
        x_label=names[index],
        y_label=names[index_next],
        title=distribution.lpm_template.name,
        filename=_output_path(directory, f"concentrations2D_{index}"),
    )
