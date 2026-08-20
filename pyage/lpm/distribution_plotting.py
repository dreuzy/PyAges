"""Plotting helpers for posterior LPM sample distributions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np

import pyage.tools.figures_additional as figadd

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_dist import LpmDist


def _output_path(directory: str | Path | None, filename: str) -> str | None:
    return None if directory is None else str(Path(directory) / filename)


def plot_points(distribution: "LpmDist") -> None:
    """Plot the first two parameters when the model has exactly two."""
    frame = distribution.frame
    values = [frame[name] for name in distribution.get_param_names()]
    if len(values) == 2:
        plt.scatter(values[1][1:600], values[0][1:600], c="black", s=3, marker=".")


def plot_parameter_pair(distribution: "LpmDist", keyx: str, keyy: str) -> None:
    """Plot one stored parameter against another."""
    frame = distribution.frame
    plt.scatter(frame[keyx], frame[keyy], marker="+", c="red", s=10, label="model")


def display_parameter_distributions(
    distribution: "LpmDist",
    self_method: str = "",
    lpm_reference: Any = None,
    bins: int = 30,
    lpm_2nd: "LpmDist | None" = None,
    lpm_2nd_method: str = "",
    directory: str | Path | None = None,
    display_text: bool = False,
) -> None:
    """Display parameter histograms, objectives, and pairwise projections."""
    del bins  # Kept in the compatibility API; plots use model-aware bin widths.
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


def display_parameter_priors(
    distribution: "LpmDist",
    lpm_reference: Any = None,
    bins: int = 30,
    lpm_2nd: "LpmDist | None" = None,
    lpm_2nd_method: str = "",
    directory: str | Path | None = None,
    display_text: bool = False,
    prior: Any = None,
) -> None:
    """Display parameter histograms with prior-density overlays."""
    del bins
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


def display_concentration_distributions(
    distribution: "LpmDist",
    self_method: str = "",
    concentrations_reference: Any = None,
    lpm_2nd: "LpmDist | None" = None,
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


def _finite_parameter_values(distribution: "LpmDist", name: str) -> np.ndarray:
    values = np.asarray(distribution.frame[name].tolist(), dtype=float)
    return values[np.isfinite(values)]


def _parameter_bins(
    distribution: "LpmDist", name: str, values: np.ndarray
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
    distribution: "LpmDist",
    name: str,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmDist | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    values = _finite_parameter_values(distribution, name)
    if values.size == 0:
        return
    model = distribution.lpm_template
    figadd.figure_init(xlab=name, ylab="Count", figname=model.name)
    bins = _parameter_bins(distribution, name, values)
    if bins.size < 2:
        return
    plt.hist(values, density=True, bins=bins, histtype="barstacked", label=self_method)
    if lpm_reference is not None:
        plt.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        values_2nd = _finite_parameter_values(lpm_2nd, name)
        if values_2nd.size > 0:
            plt.hist(
                values_2nd,
                density=True,
                bins=bins,
                histtype="barstacked",
                label=lpm_2nd_method,
            )
    plt.xlim(model.get_p_min(name), model.get_p_max(name))
    plt.legend()
    output = _output_path(directory, f"comp_{name}")
    if output is not None:
        figadd.figure_close(filename=output)


def _plot_obj_vs_param(
    distribution: "LpmDist",
    name: str,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmDist | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
) -> None:
    model = distribution.lpm_template
    frame = distribution.frame
    figadd.figure_init(xlab=name, ylab="obj_function", figname=model.name)
    plt.scatter(
        frame[name].tolist(),
        frame["obj_function"].tolist(),
        marker="x",
        c="blue",
        s=10,
        label=self_method,
    )
    if lpm_reference is not None:
        plt.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        other = lpm_2nd.frame
        plt.scatter(
            other[name],
            other["obj_function"],
            marker="+",
            c="red",
            s=10,
            label=lpm_2nd_method,
        )
    plt.legend()
    output = _output_path(directory, f"objfunction_{name}")
    if output is not None:
        figadd.figure_close(filename=output)


def _plot_param_pair(
    distribution: "LpmDist",
    names: list[str],
    index: int,
    self_method: str,
    lpm_reference: Any,
    lpm_2nd: "LpmDist | None",
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
    figadd.hist_scatter(
        histo=other is not None,
        histox=None if other is None else other[names[index]],
        histoy=None if other is None else other[names[index_next]],
        histolegend=lpm_2nd_method,
        scatter=True,
        scatterx=scatterx,
        scattery=scattery,
        scatterlegend=self_method,
        refx=refx,
        refy=refy,
        reflegend="reference",
        namex=names[index],
        namey=names[index_next],
        namefig=distribution.lpm_template.name,
        directory=directory,
        file=f"comp2D_{names[index]}_{names[index_next]}",
    )


def _plot_param_histogram_apriori(
    distribution: "LpmDist",
    name: str,
    lpm_reference: Any,
    lpm_2nd: "LpmDist | None",
    lpm_2nd_method: str,
    directory: str | Path | None,
    prior: Any,
) -> None:
    values = _finite_parameter_values(distribution, name)
    if values.size == 0:
        return
    model = distribution.lpm_template
    figadd.figure_init(xlab=name, ylab="Count", figname=model.name)
    bins = _parameter_bins(distribution, name, values)
    if bins.size < 2:
        return
    histogram = plt.hist(
        values, density=True, bins=bins, histtype="barstacked", label="MH"
    )
    nonzero_hist = histogram[0][histogram[0] != 0]
    prior_density = prior.MHapriori_para[name]
    nonzero_prior = prior_density[prior_density[:, 1] != 0, 1]
    rescaling = np.mean(nonzero_hist) / np.mean(nonzero_prior)
    plt.plot(prior_density[:, 0], prior_density[:, 1] * rescaling)
    if lpm_reference is not None:
        plt.axvline(lpm_reference.p[name], c="k", linewidth=2.0, label="reference")
    if lpm_2nd is not None:
        values_2nd = _finite_parameter_values(lpm_2nd, name)
        if values_2nd.size > 0:
            plt.hist(
                values_2nd,
                density=True,
                bins=bins,
                histtype="barstacked",
                label=lpm_2nd_method,
            )
    plt.xlim(model.get_p_min(name), model.get_p_max(name))
    plt.legend()
    output = _output_path(directory, f"comp_apriori{name}")
    if output is not None:
        figadd.figure_close(filename=output)


def _plot_concentration_pair(
    distribution: "LpmDist",
    index: int,
    index_next: int,
    self_method: str,
    concentrations_reference: Any,
    lpm_2nd: "LpmDist | None",
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
        else concentrations_reference.cv["concentration"][index]
    )
    refy = (
        None
        if concentrations_reference is None
        else concentrations_reference.cv["concentration"][index_next]
    )
    figadd.hist_scatter(
        histo=other is not None,
        histox=None if other is None else other[names[index]],
        histoy=None if other is None else other[names[index_next]],
        histolegend=lpm_2nd_method,
        scatter=True,
        scatterx=frame[names[index]],
        scattery=frame[names[index_next]],
        scatterlegend=self_method,
        refx=refx,
        refy=refy,
        reflegend="reference",
        namex=names[index],
        namey=names[index_next],
        namefig=distribution.lpm_template.name,
        directory=directory,
        file=f"concentrations2D_{index}",
    )
