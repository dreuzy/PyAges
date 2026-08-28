# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Diagnostic plots for LPM sample tables."""

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
    return None if directory is None else str(Path(directory) / filename)


def plot_parameter_pair(
    distribution: "LpmSampleTable",
    keyx: str,
    keyy: str,
    *,
    axis: "Axes | None" = None,
) -> None:
    """Plot one stored parameter against another."""
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
    """Display parameter histograms, objectives, and pairwise projections."""
    names = distribution.get_param_names()
    if display_text:
        print("DISTRIBUTION OF PARAMETERS")
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
    """Display parameter histograms with prior-density overlays."""
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
    """Display pairwise projections of modeled concentrations."""
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
    values = np.asarray(distribution.frame[name].tolist(), dtype=float)
    return values[np.isfinite(values)]


def _parameter_bins(
    distribution: "LpmSampleTable", name: str, values: np.ndarray
) -> np.ndarray:
    model = distribution.lpm_template
    binwidth = model.get_param_range(name) / 100
    if not np.isfinite(binwidth) or binwidth <= 0:
        return np.array([])
    return np.arange(
        min(max(values) / 2, model.get_p_min(name)),
        model.get_p_max(name) + binwidth,
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
    axis.set_xlim(model.get_p_min(name), model.get_p_max(name))
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
    axis.set_xlim(model.get_p_min(name), model.get_p_max(name))
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
