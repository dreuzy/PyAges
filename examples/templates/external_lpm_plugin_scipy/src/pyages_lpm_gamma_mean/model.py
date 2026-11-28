# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# SPDX-License-Identifier: CECILL-2.1
# Maintained reference example for authors of external PyAges LPM packages.

"""Gamma LPM whose standard probability functions are delegated to SciPy.

The module illustrates the short path for a law already available from
``scipy.stats``. PyAges retains meaningful public parameters and the
distribution-specific convolution formula; SciPy supplies the generic PDF,
CDF, inverse CDF, mean, and standard deviation implementations.

This is an executable integration example, not a scientifically qualified
model for a particular groundwater study.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from scipy.special import gammainc
from scipy.stats import gamma

from pyages.lpm.core.lpm_scipy import LpmScipy
from pyages.lpm.extensions import LpmDefinition


class GammaMeanLpm(LpmScipy):
    """Gamma transit-time distribution parameterized by mean and shape.

    Parameters
    ----------
    mu
        Strictly positive mean transit time in years.
    shape
        Strictly positive, dimensionless gamma shape parameter.
    directory_lpm
        Root containing ``gamma_mean/params.yaml``. PyAges supplies the
        packaged directory when the plugin is built through :func:`build_lpm`.
    """

    scipy_dist = gamma

    def __init__(self, mu=10.0, shape=2.0, directory_lpm=None):
        """Initialize the public parameters, units, and metadata root.

        ``mu`` is the mean age in years and ``shape`` controls gamma skewness.
        ``directory_lpm`` must contain ``gamma_mean/params.yaml``; normal
        factory construction supplies the packaged root or a caller override.
        """
        values = {"mu": mu, "shape": shape}
        units = {"mu": "year", "shape": "-"}
        super().__init__("gamma_mean", values, units, directory_lpm)

    def _scipy_params(self) -> tuple[tuple[float], float, float]:
        """Convert public parameters to SciPy shape, location, and scale.

        Returns
        -------
        tuple
            ``((shape,), 0.0, mu / shape)``. A gamma distribution has mean
            ``shape * scale``, so this conversion preserves the public ``mu``.
        """
        shape = float(self.p["shape"])
        scale = float(self.p["mu"]) / shape
        return (shape,), 0.0, scale

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
            ``F(t)`` and ``E[T 1(T <= t)]``. Scalar input returns floats;
            array-like input preserves its shape.

        Notes
        -----
        SciPy supplies the ordinary CDF. The analytical partial first moment is
        distribution-specific, is required by continuous convolution, and
        approaches ``mu`` as age tends to infinity.
        """
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        moment = np.zeros_like(values)
        positive = values > 0.0
        if np.any(positive):
            scaled = self.p["shape"] * values[positive] / self.p["mu"]
            moment[positive] = self.p["mu"] * gammainc(
                self.p["shape"] + 1.0,
                scaled,
            )
        if values.ndim == 0:
            return float(cdf), float(moment)
        return cdf, moment


definition = LpmDefinition(
    model_class=GammaMeanLpm,
    parameter_directory=Path(__file__).parent / "data_lpm",
    api_version=1,
)
