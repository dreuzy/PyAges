"""Presentation helpers for lumped-parameter models.

The scientific model classes deliberately do not import Matplotlib.  These
helpers keep terminal and figure rendering at the edge of the package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_base import LpmBase


def display_lpm(lpm: "LpmBase", display_options: Any) -> None:
    """Print the model name and parameters when text output is enabled."""
    if not display_options.text:
        return
    print("LPM type:", lpm.name)
    print("Parameters:")
    for name, value in lpm.p.items():
        print("\t", name, "\t=", value, lpm.parameter_units[name])


def plot_lpm(lpm: "LpmBase", kind: str, display_options: Any) -> None:
    """Plot a model PDF or CDF using the configured display lifecycle."""
    if not display_options.figure:
        return

    times, values = lpm.sample_curve(kind, 1000)
    if len(times) != len(values):
        raise ValueError(
            f"Dimension mismatch: len(t)={len(times)} != len(values)={len(values)}"
        )

    plt.figure()
    plt.xlabel("t", fontsize=16, fontweight="bold")
    plt.xticks(fontsize=14)
    plt.ylabel("f(t)", fontsize=14, fontweight="bold")
    plt.yticks(fontsize=14)
    plt.title(f"{kind} of {lpm.name}", fontsize=22, fontweight="bold")
    plt.grid(True)
    plt.plot(times, values, "r", label=lpm.name)
    plt.xlim((0, max(times)))

    maximum = max(values)
    ylim = maximum * 1.1 if maximum > 0 else 1
    if np.isfinite(ylim):
        plt.ylim((0, ylim))
    display_options.figure_close_fx(f"{lpm.name}_{kind}")


def display_parameters(lpm: "LpmBase", reference: "LpmBase | None" = None) -> None:
    """Print model parameters, optionally compared with a reference model."""
    for name, value in lpm.p.items():
        if reference is None:
            print(name, "\t", f"{value:.2f}")
            continue
        reference_value = reference.p[name]
        print(
            name,
            "\t",
            "target ",
            f"{reference_value:.2f}",
            "\t calibrated",
            f"{value:.2f}",
            "\t",
            "difference rate",
            f"{value / reference_value - 1:.1e}",
        )


def display_pdf_cdf(lpm: "LpmBase", display_options: Any) -> None:
    """Display model metadata followed by its PDF and CDF."""
    display_lpm(lpm, display_options)
    plot_lpm(lpm, "pdf", display_options)
    plot_lpm(lpm, "cdf", display_options)


def display_moments(lpm: "LpmBase") -> None:
    """Print the model's named moments."""
    print("\nmoments")
    for name, value in zip(lpm.moments_name(), lpm.moments(), strict=False):
        print(name, "", value)
    print("\n")
