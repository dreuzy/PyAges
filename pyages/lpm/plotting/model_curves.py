# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""PDF and CDF plotting helpers for individual LPMs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from pyages._plotting import create_figure, finalize_figure

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

    figure, axis = create_figure(
        x_label="t",
        y_label="f(t)",
        title=f"{kind} of {lpm.name}",
    )
    axis.plot(times, values, "r", label=lpm.name)
    axis.set_xlim((0, max(times)))

    maximum = max(values)
    ylim = maximum * 1.1 if maximum > 0 else 1
    if np.isfinite(ylim):
        axis.set_ylim((0, ylim))
    finalize_figure(
        figure,
        display_options.figure_path(f"{lpm.name}_{kind}"),
        close=display_options.figure_close,
    )


def plot_pdf_cdf(lpm: "LpmBase", display_options: Any) -> None:
    """Plot a model's PDF and CDF."""
    plot_model_curve(lpm, "pdf", display_options)
    plot_model_curve(lpm, "cdf", display_options)


__all__ = ["plot_model_curve", "plot_pdf_cdf"]
