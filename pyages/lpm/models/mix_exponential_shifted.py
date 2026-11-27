# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines a water-age mixture with one exact age and one delayed
# exponential range of ages. A mixing rate controls their probability shares;
# the model exposes the full CDF and statistics while convolution evaluates the
# point mass directly and integrates the continuous component separately.

"""
LPM Mixed Shifted-Exponential distribution model.

Purpose
-------
Define a probability measure combining an exact Dirac point mass with a
shifted-exponential continuous component, used to represent bimodal travel
time distributions. Its ordinary ``pdf()`` represents only the continuous
density because the exact point mass has no finite density value.

"""

import numpy as np
from scipy.stats import expon

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models.exponential import (
    cdf_and_partial_first_moment_from_scale_shift,
)


@register_lpm("mix_exp_shifted")
class MixExponentialShiftedLpm(LpmBase):
    """Lumped Parameter Model - Mixed shifted exponential distribution."""

    convolution_strategy = ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS

    def __init__(self, rate=0.5, mu1=10, mu2=10, shift=20, directory_lpm=None):
        """
        Initialize the exact-Dirac/shifted-exponential mixture.

        Parameters
        ----------
        rate : float
            Mixing weight for the Dirac component (0 to 1).
        mu1 : float
            Location of the Dirac spike (years).
        mu2 : float
            Scale parameter for the exponential component.
        shift : float
            Shift for the exponential component.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {"rate": rate, "mu1": mu1, "mu2": mu2, "shift": shift}
        parameter_units = {"rate": "-", "mu1": "year", "mu2": "year", "shift": "year"}
        LpmBase.__init__(
            self, "mix_exp_shifted", parameter_values, parameter_units, directory_lpm
        )

    def pdf(self, t):
        """Return the weighted density of the continuous component.

        The full distribution also contains an exact Dirac mass of probability
        ``rate`` at ``mu1``. That discrete mass is represented by :meth:`cdf`
        and by the dedicated convolution strategy, not by a finite PDF value.
        """
        return (1 - self.p["rate"]) * self.continuous_pdf(t)

    def continuous_pdf(self, t):
        """Return the normalized exponential component (mass one)."""
        return expon.pdf(
            t,
            loc=self.p["mu1"] + self.p["shift"],
            scale=self.p["mu2"],
        )

    def continuous_cdf(self, t):
        """Return the CDF of the normalized exponential component."""
        values, _ = self.continuous_cdf_and_partial_first_moment(t)
        return values

    def continuous_cdf_and_partial_first_moment(self, t):
        """Return exact mass and moment of the normalized continuous component."""
        return cdf_and_partial_first_moment_from_scale_shift(
            t,
            self.p["mu2"],
            self.continuous_support_start(),
        )

    def continuous_support_start(self):
        """Return the lower support bound of the continuous component."""
        return self.p["mu1"] + self.p["shift"]

    def get_dirac_time(self):
        """Return the exact age of the discrete component."""
        return self.p["mu1"]

    def cdf(self, t):
        """Return the right-continuous CDF of the full mixed distribution."""
        values = np.asarray(t, dtype=float)
        rate = float(self.p["rate"])
        result = rate * (values >= self.p["mu1"]).astype(float) + (
            1.0 - rate
        ) * expon.cdf(
            values,
            loc=self.continuous_support_start(),
            scale=self.p["mu2"],
        )
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p):
        """Return the generalized inverse CDF of the mixed distribution."""
        probabilities = self._validated_probabilities(p)

        rate = float(self.p["rate"])
        scale = float(self.p["mu2"])
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0, 1], got {rate}")
        if scale <= 0.0:
            raise ValueError(f"mu2 must be positive, got {scale}")

        result = np.empty_like(probabilities, dtype=float)
        if rate == 1.0:
            result.fill(float(self.p["mu1"]))
        else:
            dirac_mask = (probabilities <= rate) & (rate > 0.0)
            result[dirac_mask] = float(self.p["mu1"])
            tail_mask = ~dirac_mask
            with np.errstate(divide="ignore"):
                result[tail_mask] = self.continuous_support_start() - scale * (
                    np.log1p(-probabilities[tail_mask]) - np.log1p(-rate)
                )
        return float(result) if probabilities.ndim == 0 else result

    def mean(self):
        """Return the mean age of the full mixed distribution."""
        rate = float(self.p["rate"])
        continuous_mean = self.continuous_support_start() + self.p["mu2"]
        return rate * self.p["mu1"] + (1.0 - rate) * continuous_mean

    def std(self):
        """Return the standard deviation of the full mixed distribution."""
        rate = float(self.p["rate"])
        dirac_mean = float(self.p["mu1"])
        continuous_mean = self.continuous_support_start() + self.p["mu2"]
        mean = self.mean()
        variance = rate * (dirac_mean - mean) ** 2 + (1.0 - rate) * (
            self.p["mu2"] ** 2 + (continuous_mean - mean) ** 2
        )
        return float(np.sqrt(max(0.0, variance)))
