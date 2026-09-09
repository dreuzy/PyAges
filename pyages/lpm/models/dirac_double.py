# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines a model that splits sampled water between two exact ages.
# A first age, an additional delay, and a mixing rate produce the CDF and age
# statistics; convolution evaluates both tracer responses directly, while the
# PDF uses a finite approximation only for plotting.

"""
LPM Double-Dirac distribution model.

Purpose
-------
Define a two-spike (Dirac) LPM where the spikes are separated by ``mu2`` and
mixed by ``rate``. Its discretized PDF is a finite-width approximation for
generic sampling and visualization; convolution evaluates both masses directly.

"""

import numpy as np

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models._dirac_approximation import (
    build_regularized_dirac_pdf,
)


@register_lpm("dirac_double")
class DiracDoubleLpm(LpmBase):
    """Lumped Parameter Model - Double-Dirac distribution."""

    convolution_strategy = ConvolutionStrategy.DIRAC_DOUBLE

    def __init__(self, mu1=10, mu2=5, rate=0.2, directory_lpm=None):
        """Initialize a two-atom Dirac distribution.

        Parameters
        ----------
        mu1 : float
            Age of the first atom in years.
        mu2 : float
            Additional delay from the first atom to the second, in years.
        rate : float
            Probability mass assigned to the first atom.
        directory_lpm : str or None
            Directory containing LPM parameter files.
        """
        parameter_values = {"mu1": mu1, "mu2": mu2, "rate": rate}
        parameter_units = {"mu1": "year", "mu2": "year", "rate": "-"}
        LpmBase.__init__(
            self, "dirac_double", parameter_values, parameter_units, directory_lpm
        )

    def get_dirac_double_time(self):
        """Return the ages of the first and second exact point masses."""
        return [self.p["mu1"], self.p["mu1"] + self.p["mu2"]]

    def set_interp(self):
        """Build the finite-width PDF approximation used for visualization."""
        # Common visualization width of the exact point masses.
        width = max(
            1,
            self.get_calibration_range_width("mu1") / 200,
            self.get_calibration_range_width("mu2") / 200,
        )
        # This grid is unrelated to the direct Dirac convolution algorithm.
        td = (
            1.2
            * (
                self.get_calibration_range("mu1")[1]
                + self.get_calibration_range("mu2")[1]
            )
            * np.arange(0, 201)
            / 200
        )
        self.f = build_regularized_dirac_pdf(
            td,
            centers=[self.p["mu1"], self.p["mu1"] + self.p["mu2"]],
            weights=[self.p["rate"], 1.0 - self.p["rate"]],
            width=width,
        )

    def pdf(self, t):
        """Return the regularized two-spike density used for visualization."""
        self.set_interp()
        return self.f(t)

    def cdf(self, t):
        """p=cdf(t)
        Cumulative density
        """
        values = np.asarray(t, dtype=float)
        result = self.p["rate"] * (values >= self.p["mu1"]).astype(int) + (
            1 - self.p["rate"]
        ) * (values >= self.p["mu1"] + self.p["mu2"]).astype(int)
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p):
        """Return the generalized quantile of the two-spike distribution."""
        probabilities = self._validated_probabilities(p)
        result = np.where(
            probabilities <= self.p["rate"],
            self.p["mu1"],
            self.p["mu1"] + self.p["mu2"],
        )
        return float(result) if probabilities.ndim == 0 else result

    def mean(self):
        """Return the probability-weighted mean age."""
        return self.p["rate"] * self.p["mu1"] + (1 - self.p["rate"]) * (
            self.p["mu1"] + self.p["mu2"]
        )

    def std(self):
        """Return the standard deviation of the two-atom distribution."""
        rate = np.clip(self.p["rate"], 0.0, 1.0)
        return np.sqrt(rate * (1 - rate) * (self.p["mu2"]) ** 2)
