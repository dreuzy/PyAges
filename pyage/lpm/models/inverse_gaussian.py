# -*- coding: utf-8 -*-
"""
LPM Inverse Gaussian distribution model.

Purpose
-------
Wrap the SciPy inverse Gaussian distribution as an LPM with metadata.

Reference
---------
Waugh, D., and T. Hall (2002), Age of stratospheric air: Theory, observations,
and models, Reviews of Geophysics, 40(4), 1-1-1-26,
doi:https://doi.org/10.1029/2000RG000101.

Author
------
Jean-Raynald de Dreuzy
"""

import numpy as np
import numpy.typing as npt
from scipy.special import log_ndtr, ndtr
from scipy.stats import invgauss

from pyage.lpm.core.lpm_scipy import LpmScipySafe
from pyage.lpm.core.registry import register_lpm


def scipy_params_from_mean_std(mean_age: float, std_age: float) -> tuple[float, float]:
    r"""Convert physical IG moments in years to SciPy shape and scale.

    With physical mean :math:`M>0`, standard deviation :math:`S>0`, and
    inverse-Gaussian shape :math:`\lambda=M^3/S^2`, SciPy's convention is
    ``invgauss(mu=S**2/M**2, scale=lambda)``. This mapping gives mean ``M``
    and standard deviation ``S``; SciPy's ``mu`` is dimensionless and must not
    be confused with PyAge's physical ``mu`` parameter.
    """
    if mean_age <= 0:
        raise ValueError(f"Inverse Gaussian mean_age must be positive, got {mean_age}")
    if std_age <= 0:
        raise ValueError(f"Inverse Gaussian std_age must be positive, got {std_age}")
    shape = (std_age / mean_age) ** 2
    scale = mean_age**3 / std_age**2
    return shape, scale


def cdf_and_partial_first_moment_from_mean_std(
    t: npt.ArrayLike,
    mean_age: float,
    std_age: float,
) -> tuple[npt.ArrayLike, npt.ArrayLike]:
    r"""Return the IG CDF and raw partial first moment at ages ``t``.

    PyAge uses the inverse-Gaussian density

    .. math::

       g(x)=\sqrt{\frac{\lambda}{2\pi x^3}}
       \exp\left[-\frac{\lambda(x-M)^2}{2M^2x}\right],\quad x>0,

    with :math:`M=\mathtt{mean_age}` and
    :math:`\lambda=M^3/\mathtt{std_age}^2`, all dimensional quantities being
    in years. The second result is :math:`E[X\,1(X\leq t)]` in years, not a
    conditional mean.

    Non-positive ages return zero; positive infinity returns ``(1, M)``.
    ``log_ndtr`` is used for the reflected CDF term to avoid overflow for
    narrow distributions.
    """
    scipy_params_from_mean_std(mean_age, std_age)
    values = np.asarray(t, dtype=float)
    cdf = np.zeros_like(values, dtype=float)
    first_moment = np.zeros_like(values, dtype=float)
    positive_finite = (values > 0.0) & np.isfinite(values)
    if np.any(positive_finite):
        ages = values[positive_finite]
        shape_parameter = mean_age**3 / std_age**2
        root = np.sqrt(shape_parameter / ages)
        direct = ndtr(root * (ages / mean_age - 1.0))
        reflected_log = 2.0 * shape_parameter / mean_age + log_ndtr(
            -root * (ages / mean_age + 1.0)
        )
        reflected = np.exp(np.minimum(reflected_log, 0.0))
        cdf[positive_finite] = np.clip(direct + reflected, 0.0, 1.0)
        first_moment[positive_finite] = np.clip(
            mean_age * (direct - reflected),
            0.0,
            mean_age,
        )
    positive_infinite = np.isposinf(values)
    if np.any(positive_infinite):
        cdf[positive_infinite] = 1.0
        first_moment[positive_infinite] = mean_age
    if values.ndim == 0:
        return float(cdf), float(first_moment)
    return cdf, first_moment


@register_lpm("ig")
class InverseGaussianLpm(LpmScipySafe):
    r"""Inverse-Gaussian LPM parameterized by physical moments.

    ``mu`` is mean transit time and ``sigma`` is its standard deviation, both
    in years. They are converted internally to SciPy's dimensionless shape
    and dimensional scale; see :func:`scipy_params_from_mean_std`. The support
    is strictly positive age and the distribution integrates to one on
    ``(0, infinity)``.

    The scientific convention and migration from the former SciPy-coordinate
    interpretation are documented in ``docs/scientific-methods.md`` and
    ``docs/scientific-migration-ig-decay.md``.
    """

    scipy_dist = invgauss

    def __init__(self, mu=10, sigma=2, directory_lpm=None):
        """
        Constructor.

        Parameters
        ----------
        mu : float
            Mean transit time in years.
        sigma : float
            Standard deviation of transit time in years.
        directory_lpm : str
            Directory for LPM parameter files.
        """
        parameter_values = {"mu": mu, "sigma": sigma}
        parameter_units = {"mu": "year", "sigma": "year"}
        super().__init__("ig", parameter_values, parameter_units, directory_lpm)

    def _scipy_params(self):
        shape, scale = scipy_params_from_mean_std(self.p["mu"], self.p["sigma"])
        return (shape,), 0, scale

    def cdf_and_partial_first_moment(self, t: npt.ArrayLike):
        """Return ``F(t)`` and ``E[T 1(T <= t)]`` for convolution."""
        return cdf_and_partial_first_moment_from_mean_std(
            t,
            self.p["mu"],
            self.p["sigma"],
        )
