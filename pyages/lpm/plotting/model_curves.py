# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""PDF and CDF plotting helpers for individual LPMs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import numpy as np

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase


def plot_model_curve(lpm: "LpmBase", kind: str, display_options: Any) -> None:
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


def plot_pdf_cdf(lpm: "LpmBase", display_options: Any) -> None:
    """Plot a model's PDF and CDF."""
    plot_model_curve(lpm, "pdf", display_options)
    plot_model_curve(lpm, "cdf", display_options)


__all__ = ["plot_model_curve", "plot_pdf_cdf"]
