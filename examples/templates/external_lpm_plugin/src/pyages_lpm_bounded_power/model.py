# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1
# Maintained reference example for authors of external PyAges LPM packages.

"""Bounded power-law LPM implemented directly from mathematical formulas.

The module deliberately avoids ``scipy.stats`` so that all methods required by
a custom continuous LPM remain visible in one short reference implementation.
It is executable and tested, but it is an integration example rather than a
scientifically qualified model for a particular groundwater study.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt

from pyages.lpm.core.lpm_base import LpmBase
from pyages.lpm.extensions import LpmDefinition


class BoundedPowerLpm(LpmBase):
    """Probability law with density proportional to age ``** (alpha - 1)``.

    Parameters
    ----------
    alpha
        Dimensionless shape exponent, constrained to values at least one by
        the packaged parameter schema.
    maximum_age
        Strictly positive upper support in years.
    directory_lpm
        Root containing ``bounded_power/params.yaml``. PyAges supplies the
        packaged directory when the plugin is built through :func:`build_lpm`.
    """

    def __init__(self, alpha=2.0, maximum_age=50.0, directory_lpm=None):
        """Initialize shape, finite support, units, and parameter metadata.

        ``directory_lpm`` must contain ``bounded_power/params.yaml``. Normal
        factory construction supplies the directory packaged by this plugin or
        an explicit study override.
        """
        values = {"alpha": alpha, "maximum_age": maximum_age}
        units = {"alpha": "-", "maximum_age": "year"}
        super().__init__("bounded_power", values, units, directory_lpm)

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the analytical density on the finite support.

        Ages outside ``[0, maximum_age]`` receive zero density. Scalar input
        returns a float; array-like input returns an array of identical shape.
        """
        values = np.asarray(t, dtype=float)
        x = values / self.p["maximum_age"]
        result = np.where(
            (values >= 0.0) & (values <= self.p["maximum_age"]),
            self.p["alpha"]
            / self.p["maximum_age"]
            * np.power(np.clip(x, 0.0, 1.0), self.p["alpha"] - 1.0),
            0.0,
        )
        return float(result) if values.ndim == 0 else result

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate exact cumulative probability for scalar or array-like ages.

        The result is zero below the support, ``(t / maximum_age) ** alpha``
        inside it, and one at or above the upper boundary.
        """
        values = np.asarray(t, dtype=float)
        x = np.clip(values / self.p["maximum_age"], 0.0, 1.0)
        result = np.power(x, self.p["alpha"])
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate exact quantiles after validating probabilities in ``[0, 1]``.

        Shared validation rejects non-finite or out-of-range inputs. The return
        value preserves scalar-or-array input behavior.
        """
        probabilities = self._validated_probabilities(p)
        result = self.p["maximum_age"] * np.power(
            probabilities,
            1.0 / self.p["alpha"],
        )
        return float(result) if probabilities.ndim == 0 else result

    def mean(self) -> float:
        """Return the exact full first moment in years.

        For this bounded law the result is
        ``alpha * maximum_age / (alpha + 1)``.
        """
        alpha = self.p["alpha"]
        return alpha * self.p["maximum_age"] / (alpha + 1.0)

    def std(self) -> float:
        """Return the exact standard deviation in years.

        A closed-form value avoids numerical quadrature and supplies an
        independent identity for scientific regression tests.
        """
        alpha = self.p["alpha"]
        variance = (
            alpha * self.p["maximum_age"] ** 2 / ((alpha + 1.0) ** 2 * (alpha + 2.0))
        )
        return float(np.sqrt(variance))

    def cdf_and_partial_first_moment(
        self,
        t: npt.ArrayLike,
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        """Return exact cumulative mass and raw truncated first moment.

        Parameters
        ----------
        t
            Scalar or array-like ages in years.

        Returns
        -------
        tuple
            ``F(t)`` and ``E[T 1(T <= t)]`` with shape matching the input. At
            and above ``maximum_age``, the second value equals :meth:`mean`.
        """
        values = np.asarray(t, dtype=float)
        x = np.clip(values / self.p["maximum_age"], 0.0, 1.0)
        cdf = np.power(x, self.p["alpha"])
        moment = (
            self.p["alpha"]
            / (self.p["alpha"] + 1.0)
            * self.p["maximum_age"]
            * np.power(x, self.p["alpha"] + 1.0)
        )
        if values.ndim == 0:
            return float(cdf), float(moment)
        return cdf, moment


definition = LpmDefinition(
    model_class=BoundedPowerLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
