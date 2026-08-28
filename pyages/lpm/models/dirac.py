# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
LPM Dirac (delta) distribution model.

Purpose
-------
Define a single-spike (Dirac) lumped-parameter model. Its discretized PDF is a
finite-width approximation for generic sampling and visualization; convolution
evaluates the point mass directly.

"""

import numpy as np

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models._dirac_approximation import (
    build_regularized_dirac_pdf,
)


@register_lpm("dirac")
class DiracLpm(LpmBase):
    """Lumped Parameter Model representing a single Dirac spike."""

    convolution_strategy = ConvolutionStrategy.DIRAC

    def __init__(self, mu=10, directory_lpm=None):
        """
        Initialize a Dirac LPM.

        Parameters
        ----------
        mu : float, optional
            Dirac spike location (years).
        directory_lpm : str or None
            Directory containing LPM parameter files.
        """
        parameter_values = {"mu": mu}
        parameter_units = {"mu": "year"}
        LpmBase.__init__(
            self, "dirac", parameter_values, parameter_units, directory_lpm
        )

    def get_dirac_time(self):
        """Return the Dirac spike time."""
        return self.p["mu"]

    def set_interp(self):
        """Build the finite-width PDF approximation used for visualization."""
        # Visualization width of the exact point mass.
        width = max(1, self.get_param_range("mu") / 200)
        # Sampling grid extends beyond the configured parameter bounds.
        td = 1.2 * self.get_p_max("mu") * np.arange(0, 201) / 200
        self.f = build_regularized_dirac_pdf(
            td,
            centers=[self.p["mu"]],
            weights=[1.0],
            width=width,
        )

    def pdf(self, t):
        """Return the regularized point-mass density used for visualization."""
        self.set_interp()
        return self.f(t)

    def cdf(self, t):
        """Return the cumulative distribution function at time ``t``."""
        values = np.asarray(t, dtype=float)
        result = (values >= self.p["mu"]).astype(float)
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p):
        """Return the spike location for probabilities in ``[0, 1]``."""
        probabilities = self._validated_probabilities(p)
        result = np.full_like(probabilities, float(self.p["mu"]), dtype=float)
        return float(result) if probabilities.ndim == 0 else result

    def mean(self):
        """Return the mean of the distribution."""
        return self.p["mu"]

    def std(self):
        """Return the standard deviation of the distribution."""
        return 0.0
