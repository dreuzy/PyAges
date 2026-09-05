# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the public plotting surface for water-age models.
# Callers can draw one model's PDF or CDF and inspect calibrated parameter,
# prior, and predicted-concentration samples without importing plotting modules
# individually.

"""Plotting helpers for LPM models and sample tables."""

from pyages.lpm.plotting.model_curves import plot_model_curve, plot_pdf_cdf
from pyages.lpm.plotting.sample_diagnostics import (
    plot_concentration_diagnostics,
    plot_parameter_diagnostics,
    plot_parameter_pair,
    plot_prior_comparison,
)

__all__ = [
    "plot_concentration_diagnostics",
    "plot_model_curve",
    "plot_parameter_diagnostics",
    "plot_parameter_pair",
    "plot_pdf_cdf",
    "plot_prior_comparison",
]
