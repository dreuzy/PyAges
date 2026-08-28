# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Text summaries and diagnostic orchestration for individual LPMs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase


def print_model_summary(lpm: "LpmBase", display_options: Any) -> None:
    """Print the model name and parameters when text output is enabled."""
    if not display_options.text:
        return
    print("LPM type:", lpm.name)
    print("Parameters:")
    for name, value in lpm.p.items():
        print("\t", name, "\t=", value, lpm.parameter_units[name])


def print_parameter_comparison(
    lpm: "LpmBase", reference: "LpmBase | None" = None
) -> None:
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


def print_moment_summary(lpm: "LpmBase") -> None:
    """Print the model's named moments."""
    print("\nmoments")
    for name, value in zip(lpm.moments_name(), lpm.moments(), strict=False):
        print(name, "", value)
    print("\n")


def run_model_diagnostic(lpm_type: str, display_options: Any) -> None:
    """Build a randomized model and render the requested diagnostic outputs."""
    from pyages.lpm.factory import build_random_lpm
    from pyages.lpm.plotting.model_curves import plot_pdf_cdf

    lpm = build_random_lpm(lpm_type)
    lpm.moments()
    if display_options.figure:
        plot_pdf_cdf(lpm, display_options)
    if display_options.text:
        print_model_summary(lpm, display_options)
        print_moment_summary(lpm)


__all__ = [
    "print_model_summary",
    "print_moment_summary",
    "print_parameter_comparison",
    "run_model_diagnostic",
]
