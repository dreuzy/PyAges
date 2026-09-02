# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines an exponential water-age model with a minimum transit time.
# A shift excludes younger water and a scale controls the decreasing older tail;
# the model returns probabilities, age statistics, and exact cumulative moments
# consumed by continuous tracer convolution.

"""
LPM Shifted Exponential distribution model.

Purpose
-------
Wrap the SciPy exponential distribution with an added shift parameter,
providing an LPM-compatible shifted exponential PDF.

"""

import numpy.typing as npt
from scipy.stats import expon

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models.exponential import (
    cdf_and_partial_first_moment_from_scale_shift,
)


@register_lpm("exp_shifted")
class ExponentialShiftedLpm(LpmScipy):
    """Lumped Parameter Model - Shifted Exponential distribution."""

    scipy_dist = expon
    convolution_strategy = ConvolutionStrategy.CONTINUOUS

    def __init__(self, mu=10, shift=10, directory_lpm=None):
        """
        Initialize a shifted-exponential transit-time distribution.

        Parameters
        ----------
        mu : float
            Mean of the exponential distribution (scale parameter).
        shift : float
            Location shift (loc parameter).
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {"mu": mu, "shift": shift}
        parameter_units = {"mu": "year", "shift": "year"}
        super().__init__(
            "exp_shifted", parameter_values, parameter_units, directory_lpm
        )

    def _scipy_params(self):
        return (), self.p["shift"], self.p["mu"]  # (args), loc, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return exact cumulative mass and raw truncated first moment."""
        return cdf_and_partial_first_moment_from_scale_shift(
            t,
            self.p["mu"],
            self.p["shift"],
        )
