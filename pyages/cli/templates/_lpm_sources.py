# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Documented model and parameter sources used by the LPM project generator.

Keeping generated scientific code here separates the files authors will edit
from filesystem orchestration in :mod:`pyages.cli.templates.lpm_template`.
The strings use ``str.format`` placeholders and doubled braces for generated
Python dictionaries and YAML inline mappings.
"""

from __future__ import annotations

from dataclasses import dataclass

SCIPY_MODEL = '''\
from __future__ import annotations

{path_import}
import numpy as np
import numpy.typing as npt
from scipy.special import gammainc
from scipy.stats import gamma

from pyages.lpm.core.lpm_scipy import LpmScipy
{registration_import}


{decorator}class {class_name}Lpm(LpmScipy):
    """Gamma transit-time distribution parameterized by mean and shape.

    Parameters
    ----------
    mu
        Mean transit time in years. It must remain strictly positive.
    shape
        Dimensionless gamma shape parameter. It must remain strictly positive.
    directory_lpm
        Optional root containing ``{name}/params.yaml``. PyAges normally
        supplies this path from the built-in or plugin registration.

    Notes
    -----
    This is a complete working starter, not a scientifically validated model.
    Replace the gamma law or rename its parameters when implementing another
    distribution, and add domain-specific validation tests.
    """

    scipy_dist = gamma

    def __init__(self, mu=10.0, shape=2.0, directory_lpm=None):
        """Initialize the public parameterization and metadata location.

        ``mu`` and ``shape`` are convenient scientific parameters exposed to
        configuration and calibration. ``directory_lpm`` is the root that
        contains ``{name}/params.yaml``; normal factory construction supplies
        either the packaged root or the caller's explicit override.
        """
        values = {{"mu": mu, "shape": shape}}
        units = {{"mu": "year", "shape": "-"}}
        super().__init__("{name}", values, units, directory_lpm)

    def _scipy_params(self):
        """Translate mean and shape to SciPy's distribution convention.

        Returns
        -------
        tuple
            ``((shape,), 0.0, mu / shape)`` for SciPy's shape arguments,
            location, and scale. This preserves the public mean because a
            gamma distribution has mean ``shape * scale``.
        """
        scale = self.p["mu"] / self.p["shape"]
        return (self.p["shape"],), 0.0, scale

    def cdf_and_partial_first_moment(
        self, t: npt.ArrayLike
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        """Return ``F(t)`` and ``E[T 1(T <= t)]`` for convolution.

        Parameters
        ----------
        t
            Scalar or array-like non-negative ages in years.

        Returns
        -------
        tuple
            Cumulative probability and unnormalized first moment below each
            age. Scalar input produces two floats; array input preserves shape.

        Both results preserve the scalar-or-array shape of ``t``. Continuous
        PyAges models need this analytical partial moment in addition to the
        ordinary SciPy distribution methods. The moment tends to ``mu`` as age
        tends to infinity.
        """
        values = np.asarray(t, dtype=float)
        cdf = np.asarray(self.cdf(values), dtype=float)
        moment = np.zeros_like(values)
        positive = values > 0.0
        if np.any(positive):
            scaled = self.p["shape"] * values[positive] / self.p["mu"]
            moment[positive] = self.p["mu"] * gammainc(
                self.p["shape"] + 1.0, scaled
            )
        if values.ndim == 0:
            return float(cdf), float(moment)
        return cdf, moment
'''

ROOT_MODEL = '''\
from __future__ import annotations

{path_import}
import numpy as np
import numpy.typing as npt

from pyages.lpm.core.lpm_base import LpmBase
{registration_import}


{decorator}class {class_name}Lpm(LpmBase):
    """Bounded power-law transit times, implemented without ``scipy.stats``.

    The density is ``alpha / maximum_age * (t / maximum_age) ** (alpha - 1)``
    on ``[0, maximum_age]`` and zero elsewhere.

    Parameters
    ----------
    alpha
        Dimensionless shape exponent. The generated schema constrains it to
        values greater than or equal to one.
    maximum_age
        Finite upper support in years. It must remain strictly positive.
    directory_lpm
        Optional root containing ``{name}/params.yaml``. PyAges normally
        supplies this path from the built-in or plugin registration.

    Notes
    -----
    This complete law demonstrates every method required by a custom
    continuous LPM. Replace its formulas and scientific tests together.
    """

    def __init__(self, alpha=2.0, maximum_age=50.0, directory_lpm=None):
        """Initialize shape, finite support, units, and parameter metadata.

        ``directory_lpm`` is the root containing ``{name}/params.yaml``. The
        factory normally supplies the packaged directory or an explicit study
        override, so plugin users do not pass it directly.
        """
        values = {{"alpha": alpha, "maximum_age": maximum_age}}
        units = {{"alpha": "-", "maximum_age": "year"}}
        super().__init__("{name}", values, units, directory_lpm)

    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the bounded analytical probability density.

        Ages outside ``[0, maximum_age]`` have zero density. Scalar input
        returns a float; array-like input returns an array of identical shape.
        """
        values = np.asarray(t, dtype=float)
        x = values / self.p["maximum_age"]
        result = np.where(
            (values >= 0.0) & (values <= self.p["maximum_age"]),
            self.p["alpha"] / self.p["maximum_age"]
            * np.power(np.clip(x, 0.0, 1.0), self.p["alpha"] - 1.0),
            0.0,
        )
        return float(result) if values.ndim == 0 else result

    def cdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """Evaluate the exact cumulative probability at one or several ages.

        The result is zero below the support, ``(t / maximum_age) ** alpha``
        inside it, and one at or above the finite upper support. Input shape is
        preserved.
        """
        values = np.asarray(t, dtype=float)
        x = np.clip(values / self.p["maximum_age"], 0.0, 1.0)
        result = np.power(x, self.p["alpha"])
        return float(result) if values.ndim == 0 else result

    def cdf_inv(self, p: npt.ArrayLike) -> npt.ArrayLike:
        """Return exact quantiles for probabilities in the closed unit interval.

        Shared validation rejects non-finite values and probabilities outside
        ``[0, 1]`` before the analytical inverse is evaluated. Scalar input
        returns a float and array input preserves shape.
        """
        probabilities = self._validated_probabilities(p)
        result = self.p["maximum_age"] * np.power(
            probabilities, 1.0 / self.p["alpha"]
        )
        return float(result) if probabilities.ndim == 0 else result

    def mean(self) -> float:
        """Return the exact full first moment in years.

        For density proportional to ``t ** (alpha - 1)`` on the finite support,
        the mean is ``alpha * maximum_age / (alpha + 1)``.
        """
        alpha = self.p["alpha"]
        return alpha * self.p["maximum_age"] / (alpha + 1.0)

    def std(self) -> float:
        """Return the exact standard deviation in years.

        The closed form avoids numerical quadrature and provides an independent
        quantity for probability-contract and scientific regression tests.
        """
        alpha = self.p["alpha"]
        variance = (
            alpha
            * self.p["maximum_age"] ** 2
            / ((alpha + 1.0) ** 2 * (alpha + 2.0))
        )
        return float(np.sqrt(variance))

    def cdf_and_partial_first_moment(
        self, t: npt.ArrayLike
    ) -> tuple[npt.ArrayLike, npt.ArrayLike]:
        """Return ``F(t)`` and ``E[T 1(T <= t)]`` for convolution.

        Parameters
        ----------
        t
            Scalar or array-like ages in years.

        Returns
        -------
        tuple
            Exact cumulative mass and unnormalized first moment below each age,
            with scalar-or-array behavior matching the input.

        The second result is the unnormalized first moment below ``t``. It
        converges to :meth:`mean` above the finite support.
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
'''

SCIPY_PARAMS = """\
# Generated by ``pyages new lpm {name}``.
# Keep parameter names synchronized with the model constructor and formulas.
# Review domains, calibration ranges, priors, units, and initial values before use.
# ``domain`` is mathematical validity; ``min_inclusive: false`` excludes its
# lower boundary. ``calibration_range`` is the finite interval to explore.

model: {name}
version: 1
parameters:
  - name: mu
    label: mean_age
    unit: year
    description: Mean transit time.
    domain: {{min: 0.0, min_inclusive: false, max: null}}
    calibration_range: [0.1, 200.0]
    init: 10.0
    step: 1.0
    prior: {{type: uniform, min: 0.1, max: 200.0, unit: year}}
  - name: shape
    label: gamma_shape
    unit: "-"
    description: Dimensionless gamma shape.
    domain: {{min: 0.0, min_inclusive: false, max: null}}
    calibration_range: [0.2, 20.0]
    init: 2.0
    step: 0.2
    prior: {{type: uniform, min: 0.2, max: 20.0, unit: "-"}}
"""

ROOT_PARAMS = """\
# Generated by ``pyages new lpm {name}``.
# Keep parameter names synchronized with the model constructor and formulas.
# Review domains, calibration ranges, priors, units, and initial values before use.
# ``domain`` is mathematical validity. An inclusive boundary is allowed;
# ``min_inclusive: false`` excludes it. ``calibration_range`` is operational.

model: {name}
version: 1
parameters:
  - name: alpha
    label: power_shape
    unit: "-"
    description: Shape exponent of the bounded power law.
    domain: {{min: 1.0, min_inclusive: true, max: null}}
    calibration_range: [1.0, 8.0]
    init: 2.0
    step: 0.2
    prior: {{type: uniform, min: 1.0, max: 8.0, unit: "-"}}
  - name: maximum_age
    label: maximum_age
    unit: year
    description: Finite upper support of the distribution.
    domain: {{min: 0.0, min_inclusive: false, max: null}}
    calibration_range: [1.0, 200.0]
    init: 50.0
    step: 2.0
    prior: {{type: uniform, min: 1.0, max: 200.0, unit: year}}
"""


@dataclass(frozen=True, slots=True)
class LpmTemplateVariant:
    """Keep every base-specific generated artifact synchronized.

    ``model_source`` and ``parameter_source`` are format strings rendered with
    the selected model name. ``plugin_dependencies`` is inserted into
    ``pyproject.toml`` and ``readme_explanation`` tells authors which numerical
    operations the chosen base already supplies. Grouping these values prevents
    independent lookup tables from silently drifting apart.
    """

    model_source: str
    parameter_source: str
    plugin_dependencies: str
    readme_explanation: str


TEMPLATE_VARIANTS = {
    "scipy": LpmTemplateVariant(
        model_source=SCIPY_MODEL,
        parameter_source=SCIPY_PARAMS,
        plugin_dependencies=('["pyages>=1.0,<2", "numpy>=2,<3", "scipy>=1.14,<1.19"]'),
        readme_explanation=(
            "SciPy supplies the standard probability functions; review "
            "`_scipy_params()` and the analytical partial first moment."
        ),
    ),
    "root": LpmTemplateVariant(
        model_source=ROOT_MODEL,
        parameter_source=ROOT_PARAMS,
        plugin_dependencies='["pyages>=1.0,<2", "numpy>=2,<3"]',
        readme_explanation=(
            "The model implements every probability function directly with NumPy."
        ),
    ),
}

__all__ = ["LpmTemplateVariant", "TEMPLATE_VARIANTS"]
