# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file adapts SciPy probability distributions to the common LPM contract.
# It converts a model's physical parameters into SciPy shape, location, and scale
# inputs and returns PDFs, CDFs, quantiles, means, and standard deviations, while
# exact partial moments needed by convolution remain model-specific.

"""Adapt continuous SciPy distributions to the PyAges LPM interface.

This module is the intermediate layer between :class:`LpmBase`, which defines
the domain-facing contract of a lumped parameter model, and
``scipy.stats.rv_continuous``, which supplies well-tested distribution
algorithms.  A concrete model retains PyAges parameter names, units, metadata,
calibration behaviour, and convolution methods; it only has to select a
``scipy_dist`` and translate its physical parameters to SciPy's
``(shape_args, loc, scale)`` convention in ``_scipy_params()``.

Summary
-------
1. ``LpmScipy`` inherits the common model and parameter contract from
   :class:`LpmBase`.
2. It delegates the PDF, CDF, inverse CDF, mean, and standard deviation to a
   concrete ``scipy.stats`` continuous distribution.
3. ``_scipy_params()`` isolates the translation between PyAges's scientific
   parameterization and SciPy's shape, location, and scale coordinates.
4. Inverse-CDF inputs still pass through PyAges's shared probability validation.
5. Distribution-specific cumulative partial moments remain in the concrete
   models because they encode the analytical convolution formula, not merely
   the generic ``scipy.stats`` interface.

Effective users
---------------
The direct ``LpmScipy`` adapter is used by the registered models
``exp`` (:class:`~pyages.lpm.models.exponential.ExponentialLpm`),
``exp_shifted``
(:class:`~pyages.lpm.models.exponential_shifted.ExponentialShiftedLpm`),
``gamma`` (:class:`~pyages.lpm.models.gamma.GammaLpm`), ``uniform``
(:class:`~pyages.lpm.models.uniform.UniformLpm`), and ``weibull``
(:class:`~pyages.lpm.models.weibull.WeibullLpm`). The ``ig`` and ``ig_shifted``
models also inherit this adapter through a private inverse-Gaussian base in
``pyages.lpm.models``. Thus seven registered LPMs use this layer, backed by five
SciPy families: ``expon``, ``gamma``, ``uniform``, ``weibull_min``, and
``invgauss``.

Why this layer matters
----------------------
Keeping this adapter separate prevents every model from reimplementing the
same five statistical operations and gives them identical vectorization,
boundary, and probability-validation behaviour.  More importantly, it keeps
SciPy conventions out of the public LPM API.  This is especially useful for
the inverse Gaussian: PyAges exposes a physical mean and standard deviation in
years, whereas SciPy expects a dimensionless shape and a scale.  The model can
perform that conversion in one place while all generic numerical operations
remain centralized here.  New SciPy-backed distributions consequently need
only a small parameter adapter plus any genuinely distribution-specific
convolution formula. Numerical workarounds that apply to one SciPy family
belong in that model family rather than in this generic core adapter.
"""

import abc

import numpy as np
import numpy.typing as npt
from scipy.stats import rv_continuous

from pyages.lpm.core.lpm_base import LpmBase


class LpmScipy(LpmBase):
    """
    Base class for LPM models based on scipy.stats distributions.

    Subclasses must define:
    - scipy_dist: class attribute with the scipy.stats distribution
    - _scipy_params(): method returning (args, loc, scale) for scipy calls

    This eliminates repetitive pdf/cdf/cdf_inv/mean/std implementations.
    """

    scipy_dist: rv_continuous = None  # Override in subclass

    @abc.abstractmethod
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
        raise NotImplementedError

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Probability Density Function."""
        args, loc, scale = self._scipy_params()
        return self.scipy_dist.pdf(t, *args, loc=loc, scale=scale)

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Cumulative Density Function."""
        args, loc, scale = self._scipy_params()
        return self.scipy_dist.cdf(t, *args, loc=loc, scale=scale)

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the generalized inverse CDF for probabilities in ``[0, 1]``."""
        args, loc, scale = self._scipy_params()
        probabilities = self._validated_probabilities(p)
        return self.scipy_dist.ppf(probabilities, *args, loc=loc, scale=scale)

    def mean(self) -> float:
        """Return the finite, non-negative mean of the distribution.

        SciPy's value is returned without changing its sign. A negative or
        non-finite mean indicates a parameterization incompatible with PyAges's
        non-negative transit-time contract and is rejected explicitly.
        """
        args, loc, scale = self._scipy_params()
        mean = float(self.scipy_dist.stats(*args, loc=loc, scale=scale, moments="m"))
        if not np.isfinite(mean) or mean < 0.0:
            raise ValueError(
                f"SciPy-backed LPM '{self.name}' must have a finite, "
                f"non-negative mean, got {mean}"
            )
        return mean

    def std(self) -> float:
        """Return standard deviation of distribution."""
        args, loc, scale = self._scipy_params()
        return np.sqrt(self.scipy_dist.stats(*args, loc=loc, scale=scale, moments="v"))
