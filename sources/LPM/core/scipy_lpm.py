# -*- coding: utf-8 -*-
"""
Scipy-based LPM base class.

Provides a base class for LPM models that wrap scipy.stats distributions,
reducing code duplication across exponential, gamma, inverse gaussian,
and uniform models.
"""

from abc import abstractmethod
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.stats import rv_continuous

from LPM.core.LPM_root import LPM


class ScipyLPM(LPM):
    """
    Base class for LPM models based on scipy.stats distributions.

    Subclasses must define:
    - scipy_dist: class attribute with the scipy.stats distribution
    - _scipy_params(): method returning (args, loc, scale) for scipy calls

    This eliminates repetitive pdf/cdf/cdf_inv/mean/std implementations.
    """

    scipy_dist: rv_continuous = None  # Override in subclass

    def _scipy_params(self) -> tuple[tuple, float, float]:
        """
        Return scipy distribution parameters.

        Returns
        -------
        tuple
            (args, loc, scale) where:
            - args: tuple of shape parameters (can be empty)
            - loc: location parameter
            - scale: scale parameter
        """
        raise NotImplementedError("Subclasses must implement _scipy_params()")

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Probability Density Function."""
        args, loc, scale = self._scipy_params()
        return self.scipy_dist.pdf(t, *args, loc=loc, scale=scale)

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Cumulative Density Function."""
        args, loc, scale = self._scipy_params()
        return self.scipy_dist.cdf(t, *args, loc=loc, scale=scale)

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Inverse of the Cumulative Density Function (quantile function)."""
        args, loc, scale = self._scipy_params()
        return self.scipy_dist.ppf(p, *args, loc=loc, scale=scale)

    def mean(self) -> float:
        """Return mean of distribution."""
        args, loc, scale = self._scipy_params()
        return abs(self.scipy_dist.stats(*args, loc=loc, scale=scale, moments='m'))

    def std(self) -> float:
        """Return standard deviation of distribution."""
        args, loc, scale = self._scipy_params()
        return np.sqrt(self.scipy_dist.stats(*args, loc=loc, scale=scale, moments='v'))


class ScipyLPMSafe(ScipyLPM):
    """
    ScipyLPM with safe cdf_inv that clips probabilities.

    Useful for distributions like inverse gaussian where extreme
    probability values can cause numerical issues.
    """

    cdf_inv_eps: float = 1e-12  # Safety margin for probability clipping

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Inverse CDF with probability clipping for numerical stability."""
        args, loc, scale = self._scipy_params()
        p_safe = np.clip(p, self.cdf_inv_eps, 1 - self.cdf_inv_eps)
        return self.scipy_dist.ppf(p_safe, *args, loc=loc, scale=scale)
