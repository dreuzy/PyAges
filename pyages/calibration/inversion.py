# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes deterministic LPM inversion with an explicit residual
# objective, independent comparison metrics, and complete optimizer provenance.

"""Run deterministic LPM inversion against a prepared calibration problem.

The physical forward model belongs to :class:`CalibrationProblem`; the
objective used to select one solution is supplied separately as an
:class:`~pyages.calibration.objective.ObjectiveSpec`.  Posterior sampling keeps
its existing Gaussian target and does not use this deterministic entry point.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import numpy as np
from scipy.optimize import minimize

from pyages.calibration.objective import (
    ObjectiveSpec,
    comparison_metrics,
    scaled_residuals,
)
from pyages.calibration.problem import CalibrationProblem

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase

OptimizerName = Literal["powell", "nelder-mead", "l-bfgs-b"]
ParameterValues: TypeAlias = Mapping[str, float] | Sequence[float]

_SCIPY_METHODS: dict[OptimizerName, str] = {
    "powell": "Powell",
    "nelder-mead": "Nelder-Mead",
    "l-bfgs-b": "L-BFGS-B",
}
_DEFAULT_OPTIONS: dict[OptimizerName, dict[str, float | int]] = {
    "powell": {"xtol": 1e-8, "ftol": 1e-10, "maxiter": 2000},
    "nelder-mead": {"xatol": 1e-8, "fatol": 1e-8, "maxiter": 2000},
    "l-bfgs-b": {"ftol": 1e-12, "maxiter": 2000},
}


def _immutable_mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return an immutable detached mapping for a public result record."""
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class ResidualRecord:
    """One observation and its residuals at the selected optimum.

    ``residual`` is ``modeled - observed`` in concentration units.
    ``relative_residual`` divides that value by the absolute observation (with
    the configured floor), while ``standardized_residual`` divides it by the
    reported one-standard-deviation uncertainty. ``observation_key`` preserves
    the prepared problem's tracer/date identity and ordering.
    """

    observation_key: str
    observed: float
    modeled: float
    error: float
    residual: float
    relative_residual: float
    standardized_residual: float

    def to_dict(self) -> dict[str, str | float]:
        """Return a detached JSON-compatible residual record."""
        return {
            "observation_key": self.observation_key,
            "observed": self.observed,
            "modeled": self.modeled,
            "error": self.error,
            "residual": self.residual,
            "relative_residual": self.relative_residual,
            "standardized_residual": self.standardized_residual,
        }


@dataclass(frozen=True, slots=True)
class InversionAttempt:
    """Auditable outcome of one optimizer start.

    ``initial_parameters`` and a valid returned ``parameters`` mapping use the
    LPM's canonical parameter order. ``parameters`` is ``None`` when the
    optimizer returns a malformed or non-finite candidate. ``success`` requires
    both the optimizer success flag and a valid candidate whose objective can
    be recomputed; ``objective_value`` never trusts an optimizer-reported
    cached value.
    """

    initial_parameters: Mapping[str, float]
    parameters: Mapping[str, float] | None
    objective_value: float
    success: bool
    status: int
    message: str
    iterations: int
    evaluations: int
    runtime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Return detached JSON-compatible optimizer provenance."""
        return {
            "initial_parameters": dict(self.initial_parameters),
            "parameters": (None if self.parameters is None else dict(self.parameters)),
            "objective_value": (
                self.objective_value if np.isfinite(self.objective_value) else None
            ),
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "iterations": self.iterations,
            "evaluations": self.evaluations,
            "runtime_seconds": self.runtime_seconds,
        }


@dataclass(frozen=True, slots=True)
class InversionResult:
    """Selected deterministic solution with comparison and audit data.

    The result selects the lowest finite objective among successful attempts.
    If no optimizer reports success, it retains the best finite failed attempt
    with ``success=False`` so callers can inspect it rather than losing the
    numerical evidence. Parameter, metric, and option mappings are detached
    read-only snapshots; :meth:`to_dict` creates a mutable JSON-compatible
    representation. ``target_sha256`` identifies the prepared scientific
    target on which all starts were evaluated.
    """

    parameters: Mapping[str, float]
    objective: ObjectiveSpec
    objective_value: float
    metrics: Mapping[str, float]
    residuals: tuple[ResidualRecord, ...]
    optimizer: OptimizerName
    optimizer_options: Mapping[str, Any]
    success: bool
    status: int
    message: str
    iterations: int
    evaluations: int
    runtime_seconds: float
    best_attempt_index: int
    attempts: tuple[InversionAttempt, ...]
    target_sha256: str

    @property
    def objective_name(self) -> str:
        """Return the stable loss-and-scale identifier."""
        return self.objective.name

    @property
    def chi_square(self) -> float:
        """Return the uncertainty-standardized squared residual sum."""
        return float(self.metrics["chi_square"])

    @property
    def normalized_residual_rms(self) -> float:
        r"""Return :math:`\sqrt{\chi^2/n}` without a degrees-of-freedom correction."""
        return float(self.metrics["normalized_residual_rms"])

    def summary(self) -> dict[str, str | float | bool]:
        """Return the explicit scalar objective and comparison fields.

        ``obj_function`` is retained as a compatibility alias for the
        historical workflow diagnostic ``normalized_residual_rms``. It is not
        the selected deterministic ``objective_value`` except by coincidence.
        """
        return {
            "objective_name": self.objective_name,
            "objective_value": float(self.objective_value),
            "loss": self.objective.loss,
            "scale": self.objective.scale,
            "relative_floor": float(self.objective.relative_floor),
            "chi_square": self.chi_square,
            "normalized_residual_rms": self.normalized_residual_rms,
            "obj_function": self.normalized_residual_rms,
            "success": self.success,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible inversion result."""
        return {
            "parameters": dict(self.parameters),
            "objective": self.objective.to_dict(),
            **self.summary(),
            "metrics": dict(self.metrics),
            "residuals": [record.to_dict() for record in self.residuals],
            "optimizer": self.optimizer,
            "optimizer_options": dict(self.optimizer_options),
            "status": self.status,
            "message": self.message,
            "iterations": self.iterations,
            "evaluations": self.evaluations,
            "runtime_seconds": self.runtime_seconds,
            "best_attempt_index": self.best_attempt_index,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "target_sha256": self.target_sha256,
        }


def _parameter_vector(
    values: ParameterValues,
    *,
    names: Sequence[str],
) -> np.ndarray:
    """Return one finite vector in canonical LPM parameter order.

    A mapping is reordered by ``names`` and must contain exactly those keys; a
    sequence is assumed to already follow that order.
    """
    if isinstance(values, Mapping):
        missing = sorted(set(names) - set(values))
        extra = sorted(set(values) - set(names))
        if missing or extra:
            raise ValueError(
                "Initial parameter names must exactly match the LPM "
                f"(missing={missing}, extra={extra})"
            )
        raw = [values[name] for name in names]
    else:
        raw = values
    try:
        vector = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Initial parameters must be numeric") from exc
    if vector.shape != (len(names),):
        raise ValueError(
            f"Expected {len(names)} initial parameters, got shape {vector.shape}"
        )
    if not np.all(np.isfinite(vector)):
        raise ValueError("Initial parameters must be finite")
    return vector


def _resolved_starts(
    problem: CalibrationProblem,
    starts: Sequence[ParameterValues] | None,
) -> tuple[np.ndarray, ...]:
    """Return detached starts that lie within every calibration range.

    When ``starts`` is omitted, the initial values declared by the LPM parameter
    configuration are used as the single start.
    """
    problem.ensure_prepared()
    assert problem.lpm is not None
    names = problem.lpm.get_param_names()
    requested: Sequence[ParameterValues]
    if starts is None:
        requested = [problem.lpm.param_init()]
    else:
        if len(starts) == 0:
            raise ValueError("starts must contain at least one parameter vector")
        requested = starts
    resolved = tuple(_parameter_vector(value, names=names) for value in requested)
    for vector in resolved:
        if not problem.lpm.param_within_calibration_range_array(vector):
            raise ValueError(
                "Initial parameters must lie inside every calibration range: "
                f"{vector.tolist()}"
            )
    return resolved


def _optimizer_options(
    optimizer: OptimizerName,
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge detached caller overrides over deterministic optimizer defaults."""
    effective: dict[str, Any] = dict(_DEFAULT_OPTIONS[optimizer])
    if options is not None:
        effective.update(dict(options))
    return effective


def _optimizer_candidate(
    raw: Any,
    *,
    parameter_names: Sequence[str],
) -> tuple[np.ndarray, Mapping[str, float] | None]:
    """Normalize an optimizer candidate and flag malformed output with ``None``."""
    try:
        candidate = np.asarray(raw, dtype=float)
    except (TypeError, ValueError):
        return np.asarray([], dtype=float), None
    if candidate.shape != (len(parameter_names),) or not np.all(np.isfinite(candidate)):
        return candidate, None
    parameters = _immutable_mapping(
        dict(zip(parameter_names, candidate.tolist(), strict=True))
    )
    return candidate, parameters


def _residual_records(
    problem: CalibrationProblem,
    observed: np.ndarray,
    modeled: np.ndarray,
    errors: np.ndarray,
    *,
    relative_floor: float,
) -> tuple[ResidualRecord, ...]:
    """Build one immutable raw, relative, and standardized residual per row."""
    relative = scaled_residuals(
        observed,
        modeled,
        errors,
        scale="relative",
        relative_floor=relative_floor,
    )
    standardized = scaled_residuals(
        observed,
        modeled,
        errors,
        scale="uncertainty",
        relative_floor=relative_floor,
    )
    raw = modeled - observed
    return tuple(
        ResidualRecord(
            observation_key=key,
            observed=float(observation),
            modeled=float(prediction),
            error=float(error),
            residual=float(residual),
            relative_residual=float(relative_value),
            standardized_residual=float(standardized_value),
        )
        for key, observation, prediction, error, residual, relative_value, standardized_value in zip(
            problem.observations.observation_keys(),
            observed,
            modeled,
            errors,
            raw,
            relative,
            standardized,
            strict=True,
        )
    )


def invert_lpm(
    problem: CalibrationProblem,
    *,
    objective: ObjectiveSpec | None = None,
    optimizer: OptimizerName = "powell",
    starts: Sequence[ParameterValues] | None = None,
    options: Mapping[str, Any] | None = None,
) -> InversionResult:
    """Invert one prepared LPM using an explicit deterministic objective.

    Parameters
    ----------
    problem
        Prepared scientific target. Its committed LPM is never mutated by the
        optimization; each start receives a private working copy.
    objective
        Residual loss and scaling. The historical uncertainty-weighted squared
        L2 objective is used when omitted.
    optimizer
        Bounded SciPy optimizer: ``"powell"``, ``"nelder-mead"``, or
        ``"l-bfgs-b"``. ``"powell"`` is the derivative-free default suitable
        for paired L1/L2 comparisons; L1 is not differentiable at zero.
    starts
        Optional parameter vectors or complete name/value mappings. Every start
        must lie inside the LPM calibration ranges. The LPM YAML initial vector
        is used when omitted.
    options
        Options for the selected SciPy method. Caller values override PyAges'
        deterministic tolerances and iteration limit; both inputs and recorded
        effective options are detached from the caller's mapping.

    Returns
    -------
    InversionResult
        Best finite successful attempt when available, otherwise the best
        finite failed attempt with ``success=False``. All attempts, residuals,
        comparison metrics, and target identity remain available for review.

    Raises
    ------
    RuntimeError
        If ``problem`` is not prepared or every optimizer start returns an
        unusable candidate.
    TypeError
        If ``objective`` is neither :class:`ObjectiveSpec` nor ``None``.
    ValueError
        If the optimizer name, starts, or objective controls are invalid.

    Notes
    -----
    Each start operates on a private LPM copy, so the LPM committed to
    ``problem`` is never changed. Candidate predictions and objective values
    are recomputed from a fresh copy before selection rather than trusting
    ``OptimizeResult.fun``. This entry point performs deterministic point
    estimation only; Simplex workflow output and the FUQ/MH posterior target
    retain their historical uncertainty-weighted chi-square convention.
    """
    problem.ensure_prepared()
    if not isinstance(objective, (ObjectiveSpec, type(None))):
        raise TypeError("objective must be an ObjectiveSpec or None")
    if optimizer not in _SCIPY_METHODS:
        raise ValueError(f"Unknown optimizer: {optimizer!r}")
    assert problem.lpm is not None

    objective_spec = objective or ObjectiveSpec.pyages_default()
    observed, errors = problem.prepared_observation_arrays()
    parameter_names = problem.lpm.get_param_names()
    bounds = list(problem.lpm.get_calibration_ranges().values())
    initial_vectors = _resolved_starts(problem, starts)
    effective_options = _optimizer_options(optimizer, options)
    target_sha256 = problem.target_signature().sha256
    total_start = perf_counter()
    attempts: list[InversionAttempt] = []

    for initial in initial_vectors:
        working_lpm = deepcopy(problem.lpm)

        def evaluate(
            parameters: np.ndarray, current_lpm: LpmBase = working_lpm
        ) -> float:
            modeled = problem.predict_for_lpm(current_lpm, parameters)
            return objective_spec.evaluate(observed, modeled, errors)

        attempt_start = perf_counter()
        optimization = minimize(
            evaluate,
            initial.copy(),
            method=_SCIPY_METHODS[optimizer],
            bounds=bounds,
            options=effective_options,
        )
        attempt_runtime = perf_counter() - attempt_start
        candidate, candidate_parameters = _optimizer_candidate(
            optimization.x,
            parameter_names=parameter_names,
        )
        valid = candidate_parameters is not None and (
            problem.lpm.param_within_calibration_range_array(candidate)
        )
        recomputed = float("inf")
        if valid:
            # Verify the candidate from the physical forward model instead of
            # trusting a possibly stale or inconsistent OptimizeResult.fun.
            verification_lpm = deepcopy(problem.lpm)
            predictions = problem.predict_for_lpm(verification_lpm, candidate)
            recomputed = objective_spec.evaluate(observed, predictions, errors)
            valid = np.isfinite(recomputed)
        success = bool(optimization.success) and bool(valid)
        message = str(optimization.message)
        if not valid:
            message = f"{message}; optimizer returned an invalid candidate"
        attempts.append(
            InversionAttempt(
                initial_parameters=_immutable_mapping(
                    dict(zip(parameter_names, initial.tolist(), strict=True))
                ),
                parameters=candidate_parameters,
                objective_value=float(recomputed),
                success=success,
                status=int(getattr(optimization, "status", -1)),
                message=message,
                iterations=int(getattr(optimization, "nit", 0)),
                evaluations=int(getattr(optimization, "nfev", 0)),
                runtime_seconds=float(attempt_runtime),
            )
        )

    # Prefer a genuinely successful start. Finite failed starts remain useful
    # as explicit diagnostics when no optimizer reaches its stopping criterion.
    selectable = [
        (index, attempt)
        for index, attempt in enumerate(attempts)
        if attempt.success and np.isfinite(attempt.objective_value)
    ]
    if not selectable:
        selectable = [
            (index, attempt)
            for index, attempt in enumerate(attempts)
            if np.isfinite(attempt.objective_value)
        ]
    if not selectable:
        raise RuntimeError("Every inversion attempt returned an invalid result")
    best_index, best = min(selectable, key=lambda item: item[1].objective_value)
    if best.parameters is None:
        raise RuntimeError("The selected inversion attempt has no parameter vector")

    selected_vector = np.asarray(
        [best.parameters[name] for name in parameter_names], dtype=float
    )
    selected_lpm = deepcopy(problem.lpm)
    modeled = np.asarray(
        problem.predict_for_lpm(selected_lpm, selected_vector), dtype=float
    )
    selected_objective = objective_spec.evaluate(observed, modeled, errors)
    metrics = comparison_metrics(
        observed,
        modeled,
        errors,
        relative_floor=objective_spec.relative_floor,
    )
    runtime = perf_counter() - total_start
    return InversionResult(
        parameters=_immutable_mapping(best.parameters),
        objective=objective_spec,
        objective_value=float(selected_objective),
        metrics=_immutable_mapping(metrics),
        residuals=_residual_records(
            problem,
            observed,
            modeled,
            errors,
            relative_floor=objective_spec.relative_floor,
        ),
        optimizer=optimizer,
        optimizer_options=_immutable_mapping(effective_options),
        success=best.success,
        status=best.status,
        message=best.message,
        iterations=best.iterations,
        evaluations=best.evaluations,
        runtime_seconds=float(runtime),
        best_attempt_index=best_index,
        attempts=tuple(attempts),
        target_sha256=target_sha256,
    )


__all__ = [
    "InversionAttempt",
    "InversionResult",
    "OptimizerName",
    "ResidualRecord",
    "invert_lpm",
]
