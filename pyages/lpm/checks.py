# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Fast integration checks for built-in and externally installed LPMs.

The checks exercise the public numerical contract with deterministic parameter
sets. They catch packaging, schema, vectorization, probability, moment, and
continuous-convolution mistakes; they are not a scientific qualification of a
new transit-time model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

import numpy as np

from pyages.convolution.continuous_integration import convolve_prepared_grid
from pyages.convolution.settings import DEFAULT_CONVOLUTION_SETTINGS
from pyages.convolution.tracer_grid import PreparedTracerGrid
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.factory import build_lpm

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase

type CheckLevel = Literal["OK", "WARNING", "FAIL"]


@dataclass(frozen=True, slots=True)
class LpmCheckFinding:
    """Record one independently reported integration-check outcome.

    Parameters
    ----------
    level : {"OK", "WARNING", "FAIL"}
        Severity used by the CLI and by :attr:`LpmCheckReport.failed`.
    check : str
        Stable, human-readable check identifier such as ``"parameters"`` or
        ``"probability-1"``.
    message : str
        Successful detail, advisory explanation, or caught failure diagnostic.
    """

    level: CheckLevel
    check: str
    message: str


@dataclass(frozen=True, slots=True)
class LpmCheckReport:
    """Collect all deterministic integration findings for one model.

    A report is returned even when model construction fails. In that case its
    sole finding is a ``FAIL`` named ``construction``. Later independent checks
    are accumulated instead of stopping at the first numerical failure, which
    gives plugin authors a more useful diagnostic pass.
    """

    model_name: str
    findings: tuple[LpmCheckFinding, ...]

    @property
    def failed(self) -> bool:
        """Return ``True`` when any finding has mandatory ``FAIL`` severity."""
        return any(finding.level == "FAIL" for finding in self.findings)

    @property
    def warnings(self) -> int:
        """Count advisory or non-applicable findings without counting failures."""
        return sum(finding.level == "WARNING" for finding in self.findings)


def _array_result(value: object, shape: tuple[int, ...], name: str) -> np.ndarray:
    """Normalize one numerical result and enforce vectorization invariants.

    The checker accepts any NumPy-compatible array-like return but requires the
    exact input shape and finite floating-point values. Shape broadcasting is
    rejected because production convolution relies on elementwise alignment.
    """
    result = np.asarray(value, dtype=float)
    if result.shape != shape:
        raise ValueError(f"{name} returned shape {result.shape}, expected {shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name} returned non-finite values")
    return result


def _representative_parameter_sets(model: LpmBase) -> tuple[np.ndarray, ...]:
    """Return deterministic parameter vectors for a fast integration probe.

    The YAML initial vector is always tested. The midpoint of every calibration
    interval is added when it differs, giving limited interior coverage without
    turning the command into an expensive scientific parameter sweep.
    """
    initial = np.asarray(model.param_init(), dtype=float)
    ranges = tuple(model.get_calibration_ranges().values())
    midpoint = np.asarray([(low + high) / 2.0 for low, high in ranges], dtype=float)
    candidates = [initial]
    if not np.array_equal(initial, midpoint):
        candidates.append(midpoint)
    return tuple(candidates)


def _probability_grid(model: LpmBase) -> tuple[np.ndarray, np.ndarray]:
    """Build a deterministic age grid from quantiles and model moments.

    Quantiles at probabilities 0.1 through 0.999 check inverse-CDF ordering and
    define a practical upper age. The final dense grid combines those exact
    quantiles with zero and 257 evenly spaced ages through the larger of the
    0.999 quantile, ``mean + 8*std``, or one year.
    """
    probabilities = np.asarray([0.1, 0.5, 0.9, 0.99, 0.999], dtype=float)
    quantiles = _array_result(
        model.cdf_inv(probabilities),
        probabilities.shape,
        "cdf_inv",
    )
    if np.any(quantiles < 0.0) or np.any(np.diff(quantiles) < -1.0e-10):
        raise ValueError("cdf_inv must return non-negative, nondecreasing ages")
    upper = max(float(quantiles[-1]), float(model.mean() + 8.0 * model.std()), 1.0)
    ages = np.unique(
        np.concatenate((np.asarray([0.0]), np.linspace(0.0, upper, 257), quantiles))
    )
    return ages, quantiles


def _check_probability_contract(model: LpmBase) -> None:
    """Validate the common scalar statistics and vector probability contract.

    The probe requires finite non-negative moments, ordered non-negative
    quantiles, shape-preserving finite PDF/CDF arrays, a non-negative PDF, a CDF
    bounded by zero and one, monotonicity, practical normalization, and
    CDF/inverse-CDF consistency. Tolerances accommodate floating-point roundoff
    but not visibly different probability laws.
    """
    mean = float(model.mean())
    std = float(model.std())
    if not np.isfinite(mean) or mean < 0.0:
        raise ValueError(f"mean must be finite and non-negative, got {mean}")
    if not np.isfinite(std) or std < 0.0:
        raise ValueError(f"std must be finite and non-negative, got {std}")

    ages, quantiles = _probability_grid(model)
    cdf = _array_result(model.cdf(ages), ages.shape, "cdf")
    pdf = _array_result(model.pdf(ages), ages.shape, "pdf")
    tolerance = 1.0e-10
    if np.any(cdf < -tolerance) or np.any(cdf > 1.0 + tolerance):
        raise ValueError("cdf returned values outside [0, 1]")
    if np.any(np.diff(cdf) < -tolerance):
        raise ValueError("cdf is not nondecreasing")
    if np.any(pdf < -tolerance):
        raise ValueError("pdf returned negative values")
    if float(cdf[-1]) < 0.99:
        raise ValueError(f"cdf reaches only {cdf[-1]:.6g} on its 0.999 quantile grid")

    quantile_cdf = _array_result(model.cdf(quantiles), quantiles.shape, "cdf")
    if np.any(quantile_cdf + 1.0e-8 < np.asarray([0.1, 0.5, 0.9, 0.99, 0.999])):
        raise ValueError("cdf_inv is inconsistent with cdf")


def _affine_grid(
    edges: np.ndarray, intercept: float, slope: float
) -> PreparedTracerGrid:
    """Sample an affine synthetic tracer exactly at integration quadrature nodes.

    Constant and affine responses have analytical convolutions in terms of
    cumulative mass and the raw first moment, making them compact independent
    probes of the production continuous-integration implementation.
    """
    midpoints = 0.5 * (edges[:-1] + edges[1:])
    return PreparedTracerGrid(
        date=0.0,
        edges=edges,
        k_left=intercept + slope * edges[:-1],
        k_mid=intercept + slope * midpoints,
        k_right=intercept + slope * edges[1:],
    )


def _check_continuous_convolution(model: LpmBase) -> None:
    """Compare production continuous convolution with two analytical results.

    The check first verifies that the model's cumulative partial-moment method
    preserves shape, is finite and monotone, and returns the same CDF as
    ``model.cdf``. It then convolves constant and affine tracer responses on a
    short grid; their expected values are computed directly from interval mass
    and raw first moment.
    """
    upper_quantile = _array_result(model.cdf_inv(0.999), (), "cdf_inv")
    upper = max(float(upper_quantile.item()), 1.0)
    edges = np.linspace(0.0, upper, 9)
    cdf, moment = model.cdf_and_partial_first_moment(edges)
    cdf_array = _array_result(cdf, edges.shape, "cdf_and_partial_first_moment CDF")
    moment_array = _array_result(
        moment,
        edges.shape,
        "cdf_and_partial_first_moment moment",
    )
    if np.any(np.diff(moment_array) < -1.0e-10):
        raise ValueError("partial first moment is not nondecreasing")
    direct_cdf = _array_result(model.cdf(edges), edges.shape, "cdf")
    if not np.allclose(cdf_array, direct_cdf, rtol=1.0e-10, atol=1.0e-12):
        raise ValueError("moment provider CDF differs from cdf")

    mass = float(cdf_array[-1] - cdf_array[0])
    raw_moment = float(moment_array[-1] - moment_array[0])
    for intercept, slope, label in ((3.0, 0.0, "constant"), (2.0, 0.5, "affine")):
        result, diagnostics = convolve_prepared_grid(
            _affine_grid(edges, intercept, slope),
            model.cdf_and_partial_first_moment,
            model.name,
            DEFAULT_CONVOLUTION_SETTINGS,
        )
        expected = intercept * mass + slope * raw_moment
        if not np.isclose(result, expected, rtol=1.0e-11, atol=1.0e-11):
            raise ValueError(
                f"{label} tracer convolution returned {result}, expected {expected}"
            )
        if not np.isclose(diagnostics.window_mass, mass, atol=1.0e-12):
            raise ValueError(f"{label} tracer convolution reports the wrong mass")


def _check_strategy_contract(model: LpmBase) -> str:
    """Require the callable method family declared by a model's strategy.

    This structural probe catches a mismatched strategy before a production
    convolution reaches an attribute error. Numerical behavior is tested here
    only for the continuous strategy; specialized strategy tests remain part
    of the PyAges suite and the plugin's scientific tests.
    """
    strategy = model.convolution_strategy
    requirements: dict[ConvolutionStrategy, tuple[str, ...]] = {
        ConvolutionStrategy.CONTINUOUS: ("cdf_and_partial_first_moment",),
        ConvolutionStrategy.DIRAC: ("get_dirac_time",),
        ConvolutionStrategy.DIRAC_DOUBLE: ("get_dirac_double_time",),
        ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS: (
            "get_dirac_time",
            "continuous_cdf_and_partial_first_moment",
        ),
        ConvolutionStrategy.PIECEWISE_UNIFORM: (
            "bin_edges",
            "fractions",
        ),
    }
    if strategy not in requirements:
        raise ValueError(f"unsupported convolution strategy {strategy!r}")
    missing = [
        name
        for name in requirements[strategy]
        if not callable(getattr(model, name, None))
    ]
    if missing:
        raise ValueError(f"{strategy.name} strategy is missing methods {missing}")
    return strategy.name


def _append_check(
    findings: list[LpmCheckFinding],
    check_name: str,
    operation: Callable[[], str | None],
) -> None:
    """Run one diagnostic operation and append an ``OK`` or ``FAIL`` finding.

    Exceptions are converted to failure messages so other independent checks
    can continue. This broad catch is intentional at the diagnostic boundary;
    normal model construction and numerical APIs still raise their exceptions.
    """
    try:
        detail = operation()
    except Exception as exc:
        findings.append(LpmCheckFinding("FAIL", check_name, str(exc)))
    else:
        findings.append(LpmCheckFinding("OK", check_name, detail or "passed"))


def _check_parameter_sets(model: LpmBase) -> str:
    """Confirm representative vectors satisfy operational and mathematical bounds.

    Returns a short success message containing the number of distinct vectors
    checked; otherwise the first invalid vector is included in ``ValueError``.
    """
    parameter_sets = _representative_parameter_sets(model)
    for values in parameter_sets:
        if not model.param_within_calibration_range_array(values):
            raise ValueError(f"parameter vector outside calibration ranges: {values}")
        if not model.param_within_domain_array(values):
            raise ValueError(f"parameter vector outside mathematical domains: {values}")
    return f"{len(parameter_sets)} deterministic parameter set(s)"


def _append_model_checks(
    model: LpmBase,
    findings: list[LpmCheckFinding],
) -> None:
    """Append provenance, parameter, strategy, probability, and convolution checks.

    Probability behavior is evaluated for every representative parameter set.
    Continuous models additionally use the production integration engine;
    other strategies receive an explicit non-applicable warning rather than a
    misleading success.
    """
    if model.provenance is None:
        findings.append(LpmCheckFinding("FAIL", "provenance", "missing provenance"))
    else:
        provider = (
            f"{model.provenance.provider_distribution} "
            f"{model.provenance.provider_version}"
        )
        findings.append(LpmCheckFinding("OK", "provenance", provider))

    _append_check(findings, "parameters", lambda: _check_parameter_sets(model))
    _append_check(findings, "strategy", lambda: _check_strategy_contract(model))

    for index, values in enumerate(_representative_parameter_sets(model), start=1):

        def probability_check(values=values, index=index) -> str:
            model.set_param_from_array(values)
            _check_probability_contract(model)
            return f"parameter set {index}"

        _append_check(findings, f"probability-{index}", probability_check)

    if model.convolution_strategy == ConvolutionStrategy.CONTINUOUS:
        _append_check(
            findings,
            "constant-and-affine-convolution",
            lambda: _check_continuous_convolution(model),
        )
    else:
        findings.append(
            LpmCheckFinding(
                "WARNING",
                "constant-and-affine-convolution",
                f"not applicable to {model.convolution_strategy.name}",
            )
        )


def check_lpm(
    model_name: str,
    directory_lpm: str | Path | None = None,
) -> LpmCheckReport:
    """Run the common deterministic integration audit for one advertised LPM.

    Parameters
    ----------
    model_name : str
        Canonical built-in or installed external model name.
    directory_lpm : str, pathlib.Path, or None
        Optional parameter-root override containing
        ``<model_name>/params.yaml``. When omitted, use provider-packaged data.

    Returns
    -------
    LpmCheckReport
        Construction and post-construction findings. Expected plugin, schema,
        or numerical failures are represented in the report rather than raised.

    Notes
    -----
    The checker verifies packaging and the shared PyAges numerical contract at
    YAML initial and midpoint parameter vectors. It is deliberately fast and
    deterministic. It does not establish normalization over every parameter,
    hydrogeological relevance, identifiability, or agreement with independent
    scientific reference data; those claims require plugin-owned tests.
    """
    findings: list[LpmCheckFinding] = []

    try:
        model = build_lpm(model_name, directory_lpm=directory_lpm)
    except Exception as exc:
        return LpmCheckReport(
            model_name,
            (LpmCheckFinding("FAIL", "construction", str(exc)),),
        )
    findings.append(
        LpmCheckFinding(
            "OK",
            "construction",
            f"{type(model).__module__}.{type(model).__qualname__}",
        )
    )

    _append_model_checks(model, findings)
    return LpmCheckReport(model_name, tuple(findings))


__all__ = ["LpmCheckFinding", "LpmCheckReport", "check_lpm"]
