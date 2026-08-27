# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
LPM Double-Dirac (one fixed spike) distribution model.

Purpose
-------
Define a constrained parameterization of the Double-Dirac family where one
spike is fixed (muset) and the other is free (mufree). Its discretized PDF is a
finite-width approximation for generic sampling and visualization; convolution
evaluates both masses directly.

"""

import numpy as np

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models._dirac_approximation import (
    build_regularized_dirac_pdf,
)


@register_lpm("dirac_double_1_set")
class DiracDouble1SetLpm(LpmBase):
    """
    Constrained Double-Dirac parameterization with one fixed spike.

    This registered variant uses the same ``DIRAC_DOUBLE`` convolution
    strategy as :class:`DiracDoubleLpm`; it is not a separate scientific LPM
    family.
    """

    convolution_strategy = ConvolutionStrategy.DIRAC_DOUBLE

    def __init__(self, mufree=10, muset=70, rate=0.2, directory_lpm=None):
        """
        Initialize a double-Dirac LPM with one fixed spike.

        Parameters
        ----------
        mufree : float
            Location of the free spike (years).
        muset : float
            Location of the fixed spike (years).
        rate : float
            Mixing weight for the free spike.
        directory_lpm : str or None
            Directory containing LPM parameter files.
        """
        self.__muset = muset
        parameter_values = {"mufree": mufree, "rate": rate}
        parameter_units = {"mufree": "year", "rate": "-"}
        LpmBase.__init__(
            self, "dirac_double_1_set", parameter_values, parameter_units, directory_lpm
        )

    def get_dirac_double_time(self):
        """Return the times of the two Dirac spikes."""
        return [self.p["mufree"], self.__muset]

    def set_interp(self):
        """Build the finite-width PDF approximation used for visualization."""
        # Common visualization width of the exact point masses.
        width = max(1, self.get_param_range("mufree") / 200, self.__muset / 200)
        # This grid is unrelated to the direct Dirac convolution algorithm.
        td = 1.2 * (self.get_p_max("mufree") + self.__muset) * np.arange(0, 201) / 200
        self.f = build_regularized_dirac_pdf(
            td,
            centers=[self.p["mufree"], self.__muset],
            weights=[self.p["rate"], 1.0 - self.p["rate"]],
            width=width,
        )

    def pdf(self, t):
        """Return the regularized two-spike density used for visualization."""
        self.set_interp()
        return self.f(t)

    def cdf(self, t):
        """Return the cumulative distribution function at time ``t``."""
        values = np.asarray(t, dtype=float)
        result = self.p["rate"] * (values >= self.p["mufree"]).astype(int) + (
            1 - self.p["rate"]
        ) * (values >= self.__muset).astype(int)
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p):
        """Return the generalized quantile of the two-spike distribution."""
        probabilities = self._validated_probabilities(p)
        result = np.where(
            probabilities <= self.p["rate"],
            self.p["mufree"],
            self.__muset,
        )
        return float(result) if probabilities.ndim == 0 else result

    def mean(self):
        """Return the mean of the distribution."""
        return self.p["rate"] * self.p["mufree"] + (1 - self.p["rate"]) * self.__muset

    def std(self):
        """Return the standard deviation of the distribution."""
        return np.sqrt(
            self.p["rate"]
            * (1 - self.p["rate"])
            * (self.__muset - self.p["mufree"]) ** 2
        )
