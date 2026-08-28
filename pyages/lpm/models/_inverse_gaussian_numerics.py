# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Private numerical support shared by the two inverse-Gaussian LPMs.

This module is used by ``InverseGaussianLpm`` and
``InverseGaussianShiftedLpm``. It only handles inverse-Gaussian quantiles;
continuous convolution uses each model's analytical CDF and partial first
moment and does not use this numerical fallback.
"""

import warnings

import numpy as np
import numpy.typing as npt
from scipy.optimize import brentq
from scipy.stats import invgauss

from pyages.lpm.core.lpm_scipy import LpmScipy


class _InverseGaussianLpmBase(LpmScipy):
    """Share inverse-Gaussian-specific quantile handling between LPMs."""

    scipy_dist = invgauss

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Return exact endpoints and robust interior IG quantiles.

        SciPy's PPF is preserved for every probability strictly between zero
        and one. A scalar CDF inversion is used only when that PPF returns a
        non-finite value, which can occur for extreme inverse-Gaussian
        parameters or probabilities.
        """
        args, loc, scale = self._scipy_params()
        probabilities = self._validated_probabilities(p)
        flat_probabilities = probabilities.reshape(-1)
        quantiles = np.empty_like(flat_probabilities)

        lower_endpoint = flat_probabilities == 0.0
        upper_endpoint = flat_probabilities == 1.0
        interior = ~(lower_endpoint | upper_endpoint)
        quantiles[lower_endpoint] = loc
        quantiles[upper_endpoint] = np.inf

        if np.any(interior):
            interior_probabilities = flat_probabilities[interior]
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*inverse_gaussian_distribution.*",
                    category=RuntimeWarning,
                )
                interior_quantiles = np.asarray(
                    self.scipy_dist.ppf(
                        interior_probabilities,
                        *args,
                        loc=loc,
                        scale=scale,
                    ),
                    dtype=float,
                )

            non_finite = ~np.isfinite(interior_quantiles)
            if np.any(non_finite):
                interior_quantiles[non_finite] = [
                    self._invert_cdf(float(probability), args, loc, scale)
                    for probability in interior_probabilities[non_finite]
                ]
            quantiles[interior] = interior_quantiles

        if probabilities.ndim == 0:
            return float(quantiles[0])
        return quantiles.reshape(probabilities.shape)

    def _invert_cdf(
        self,
        probability: float,
        args: tuple,
        loc: float,
        scale: float,
    ) -> float:
        """Invert one interior probability after a non-finite SciPy PPF."""
        mean = float(self.scipy_dist.mean(*args, loc=loc, scale=scale))
        std = float(self.scipy_dist.std(*args, loc=loc, scale=scale))
        upper = loc + max(mean - loc, std, 1.0)

        while (
            float(self.scipy_dist.cdf(upper, *args, loc=loc, scale=scale)) < probability
        ):
            width = upper - loc
            if not np.isfinite(width) or width >= np.finfo(float).max / 2.0:
                raise RuntimeError(
                    "Could not bracket an inverse-Gaussian quantile for "
                    f"probability {probability}"
                )
            upper = loc + 2.0 * width

        return float(
            brentq(
                lambda age: (
                    float(self.scipy_dist.cdf(age, *args, loc=loc, scale=scale))
                    - probability
                ),
                loc,
                upper,
            )
        )
