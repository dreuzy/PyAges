# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file adds a minimum transit time to the inverse-Gaussian water-age model.
# A mean, standard deviation, and shift in years are converted to SciPy inputs;
# the resulting probabilities, robust quantiles, and cumulative moments feed
# model diagnostics and continuous tracer convolution.

"""
LPM Shifted Inverse Gaussian distribution model.

Purpose
-------
Wrap the SciPy inverse Gaussian distribution with an added shift parameter,
providing an LPM-compatible shifted inverse-Gaussian PDF.

"""

import numpy as np
import numpy.typing as npt

from pyages.lpm.core.registry import register_lpm
from pyages.lpm.models._inverse_gaussian_numerics import _InverseGaussianLpmBase
from pyages.lpm.models.inverse_gaussian import (
    cdf_and_partial_first_moment_from_mean_std,
    scipy_params_from_mean_std,
)


@register_lpm("ig_shifted")
class InverseGaussianShiftedLpm(_InverseGaussianLpmBase):
    r"""Shifted inverse-Gaussian LPM in physical moment coordinates.

    If :math:`X` has mean ``mu`` and standard deviation ``sigma`` in years,
    transit time is :math:`T=\mathtt{shift}+X`. Thus the total mean age is
    ``shift + mu``, the standard deviation remains ``sigma``, and the support
    is ``(shift, infinity)``. ``mu`` is not SciPy's dimensionless shape.

    See ``docs/scientific-methods.md`` and
    ``docs/scientific-migration-ig-decay.md`` for equations and migration
    implications.
    """

    def __init__(self, mu=10, sigma=2, shift=5, directory_lpm=None):
        """
        Initialize a shifted inverse-Gaussian transit-time distribution.

        Parameters
        ----------
        mu : float
            Mean of the dispersive component in years, excluding ``shift``.
        sigma : float
            Standard deviation of the dispersive component in years.
        shift : float
            Minimum transit-time shift in years. It is added to ``mu`` when
            reporting the mean of the complete distribution.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {"mu": mu, "sigma": sigma, "shift": shift}
        parameter_units = {"mu": "year", "sigma": "year", "shift": "year"}
        super().__init__("ig_shifted", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        shape, scale = scipy_params_from_mean_std(self.p["mu"], self.p["sigma"])
        return (shape,), self.p["shift"], scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        r"""Return the shifted CDF and raw partial first moment.

        For :math:`T=t_0+X`, the returned moment is
        :math:`E[T1(T\leq t)]=t_0F_X(t-t_0)+E[X1(X\leq t-t_0)]`, in years.
        """
        values = np.asarray(t, dtype=float)
        cdf, component_moment = cdf_and_partial_first_moment_from_mean_std(
            values - self.p["shift"],
            self.p["mu"],
            self.p["sigma"],
        )
        cdf = np.asarray(cdf, dtype=float)
        raw_moment = self.p["shift"] * cdf + np.asarray(
            component_moment,
            dtype=float,
        )
        if values.ndim == 0:
            return float(cdf), float(raw_moment)
        return cdf, raw_moment
