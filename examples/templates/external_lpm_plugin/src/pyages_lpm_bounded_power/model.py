"""Bounded power-law transit-time distribution implemented without SciPy."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase


class BoundedPowerLpm(LpmBase):
    r"""Power-law probability density on the finite interval ``[0, tau]``.

    The density is

    .. math::

       f(t) = \frac{\alpha + 1}{\tau}
              \left(\frac{t}{\tau}\right)^\alpha,
       \qquad 0 \leq t \leq \tau,

    with ``tau > 0`` and ``alpha > 0``. It is zero outside its support.

    ``tau`` is the maximum transit time. Increasing ``alpha`` moves probability
    mass toward older ages near ``tau``.
    """

    convolution_strategy = ConvolutionStrategy.CONTINUOUS

    def __init__(
        self,
        tau: float = 50.0,
        alpha: float = 2.0,
        directory_lpm=None,
    ) -> None:
        """Create the distribution and bind its calibration metadata."""
        parameter_values = {"tau": tau, "alpha": alpha}
        parameter_units = {"tau": "year", "alpha": "dimensionless"}
        super().__init__(
            "bounded_power",
            parameter_values,
            parameter_units,
            directory_lpm,
        )

    def _validated_parameters(self) -> tuple[float, float]:
        """Return finite parameters after checking the mathematical domain."""
        tau = float(self.p["tau"])
        alpha = float(self.p["alpha"])
        if not np.isfinite(tau) or tau <= 0.0:
            raise ValueError(f"tau must be positive and finite, got {tau}")
        if not np.isfinite(alpha) or alpha <= 0.0:
            raise ValueError(f"alpha must be positive and finite, got {alpha}")
        return tau, alpha

    @staticmethod
    def _return_scalar_when_needed(values: np.ndarray):
        """Preserve the scalar-or-array shape convention used by PyAges."""
        return float(values) if values.ndim == 0 else values

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the normalized probability density."""
        tau, alpha = self._validated_parameters()
        ages = np.asarray(t, dtype=float)
        reduced_age = np.clip(ages / tau, 0.0, 1.0)
        values = np.where(
            (ages >= 0.0) & (ages <= tau),
            (alpha + 1.0) / tau * reduced_age**alpha,
            0.0,
        )
        return self._return_scalar_when_needed(values)

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the cumulative distribution function."""
        tau, alpha = self._validated_parameters()
        ages = np.asarray(t, dtype=float)
        reduced_age = np.clip(ages / tau, 0.0, 1.0)
        values = reduced_age ** (alpha + 1.0)
        return self._return_scalar_when_needed(values)

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the analytical generalized inverse CDF."""
        tau, alpha = self._validated_parameters()
        probabilities = self._validated_probabilities(p)
        values = tau * probabilities ** (1.0 / (alpha + 1.0))
        return self._return_scalar_when_needed(values)

    def mean(self) -> float:
        """Return the analytical mean transit time."""
        tau, alpha = self._validated_parameters()
        return tau * (alpha + 1.0) / (alpha + 2.0)

    def std(self) -> float:
        """Return the analytical standard deviation."""
        tau, alpha = self._validated_parameters()
        first_moment = tau * (alpha + 1.0) / (alpha + 2.0)
        second_moment = tau**2 * (alpha + 1.0) / (alpha + 3.0)
        variance = second_moment - first_moment**2
        return float(np.sqrt(max(0.0, variance)))

    def cdf_and_partial_first_moment(
        self,
        t: npt.ArrayLike,
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        r"""Return ``F(t)`` and ``E[T 1(T <= t)]`` analytically.

        For an age inside the support, the raw partial first moment is

        .. math::

           M_1(t) = \tau\frac{\alpha+1}{\alpha+2}
                    \left(\frac{t}{\tau}\right)^{\alpha+2}.

        Below zero it is zero; above ``tau`` it equals the full mean.
        """
        tau, alpha = self._validated_parameters()
        ages = np.asarray(t, dtype=float)
        reduced_age = np.clip(ages / tau, 0.0, 1.0)
        cdf = reduced_age ** (alpha + 1.0)
        partial_moment = self.mean() * reduced_age ** (alpha + 2.0)

        if ages.ndim == 0:
            return float(cdf), float(partial_moment)
        return cdf, partial_moment
