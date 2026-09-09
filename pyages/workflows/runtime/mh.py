# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file translates validated workflow settings into single- or multi-chain
# Metropolis--Hastings runs and creates a fresh calibration problem per stage.

"""Shared workflow services for Metropolis--Hastings runs.

The inference engine deliberately knows nothing about workflow result paths.
This module is the integration boundary: it translates validated YAML, gives
every stage a fresh :class:`~pyages.calibration.problem.CalibrationProblem`,
runs the same orchestration for one or many chains, serializes the audit trail,
and enforces the qualification policy when inter-chain diagnostics apply.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.methods.mh.run_config import (
    MHDiagnosticsConfig,
    MHInitializationConfig,
    MHPilotConfig,
    MHRunConfig,
)
from pyages.calibration.methods.mh.runner import MetropolisHastingsRunner
from pyages.calibration.problem import CalibrationProblem
from pyages.config.models import MetropolisHastingsCfg
from pyages.data_io.mh_results import write_mh_run_result
from pyages.lpm.samples import LpmSampleTable

_ProblemBuilder = Callable[[Path], CalibrationProblem]


def build_mh_config(
    config: MetropolisHastingsCfg,
    *,
    seed: int | None = None,
    prior_option: bool | None = None,
    likelihood: bool | None = None,
    prior_type: Literal["parametric", "empirical"] = "parametric",
    prior_file: str = "",
) -> MHConfig:
    """Translate workflow settings and an optional prior source for one chain."""
    effective_seed = config.seed if seed is None else seed
    if effective_seed is None:
        effective_seed = secrets.randbits(64)
    return MHConfig(
        nsteps=config.nsteps,
        burn_in=config.burn_in,
        thinning=config.thinning,
        prior_option=config.prior_option if prior_option is None else prior_option,
        likelihood=config.likelihood if likelihood is None else likelihood,
        prior_type=prior_type,
        prior_file=prior_file,
        display_traj=config.display_traj,
        componentwise_source="model",
        seed=effective_seed,
    )


def build_mh_run_config(config: MetropolisHastingsCfg) -> MHRunConfig:
    """Return immutable one-to-many-chain controls from validated YAML."""
    explicit_starts = config.initialization.explicit_starts
    initialization = MHInitializationConfig(
        strategy=config.initialization.strategy,
        explicit_starts=(
            tuple(dict(values) for values in explicit_starts)
            if explicit_starts is not None
            else None
        ),
        max_attempts=config.initialization.max_attempts,
    )
    pilot_multiplier = config.pilot.proposal_multiplier
    pilot = MHPilotConfig(
        enabled=config.pilot.enabled,
        nsteps=config.pilot.nsteps,
        burn_in=config.pilot.burn_in,
        relative_ridge=config.pilot.relative_ridge,
        proposal_multiplier=(
            None if pilot_multiplier == "auto" else float(pilot_multiplier)
        ),
        save_samples=config.pilot.save_samples,
    )
    diagnostics = MHDiagnosticsConfig(
        max_rhat=config.diagnostics.max_rhat,
        min_bulk_ess=config.diagnostics.min_bulk_ess,
        min_tail_ess=config.diagnostics.min_tail_ess,
        require_convergence=config.diagnostics.require_convergence,
    )
    return MHRunConfig(
        chains=config.chains,
        seed=config.seed,
        initialization=initialization,
        pilot=pilot,
        diagnostics=diagnostics,
    )


def _mh_stage_directory(
    output_directory: str | Path,
    stage: str,
    chain_id: int,
) -> Path:
    """Return the stable audit directory for one MH run stage."""
    root = Path(output_directory)
    if stage == "initialization":
        if chain_id != 0:
            raise ValueError("the initialization prototype must use chain_id 0")
        return root / "initialization"
    if isinstance(chain_id, bool) or not isinstance(chain_id, int) or chain_id < 1:
        raise ValueError("pilot and production chain_id values must be positive")
    if stage == "pilot":
        return root / "pilot" / f"chain_{chain_id:03d}"
    if stage == "production":
        return root / "chains" / f"chain_{chain_id:03d}"
    raise ValueError(f"unknown MH run stage: {stage!r}")


def execute_mh_run(
    chain_config: MHConfig,
    run_config: MHRunConfig,
    output_directory: str | Path,
    problem_builder: _ProblemBuilder,
) -> LpmSampleTable:
    """Execute and persist an MH run from exact chain and run configurations.

    Inter-chain qualification is skipped explicitly for a one-chain run. For
    two or more chains, artifacts are written before a required convergence
    failure is raised, so a rejected run remains fully auditable.
    """
    if not callable(problem_builder):
        raise TypeError("problem_builder must be callable")

    root = Path(output_directory)
    runner = MetropolisHastingsRunner(chain_config, run_config)

    def problem_factory(stage: str, chain_id: int) -> CalibrationProblem:
        return problem_builder(_mh_stage_directory(root, stage, chain_id))

    record = runner.run(problem_factory)
    pooled = write_mh_run_result(
        record,
        root,
    )
    if pooled is not None:
        return pooled

    failed = ", ".join(
        diagnostic.parameter
        for diagnostic in record.diagnostics
        if diagnostic.included_in_qualification and not diagnostic.qualified
    )
    detail = failed or record.diagnostics_message or "diagnostics unavailable"
    raise MHConvergenceError(
        "Multi-chain MH did not satisfy the configured convergence gates "
        f"for: {detail}. Chain samples and diagnostics were preserved."
    )


def run_mh_calibration(
    config: MetropolisHastingsCfg,
    output_directory: str | Path,
    problem_builder: _ProblemBuilder,
) -> LpmSampleTable:
    """Run one or many chains through the same auditable MH orchestration."""
    run_config = build_mh_run_config(config)
    if run_config.seed is None:  # defensive; MHRunConfig realizes it
        raise AssertionError("validated MH run config has no seed")
    chain_config = build_mh_config(config, seed=run_config.seed)
    return execute_mh_run(
        chain_config,
        run_config,
        output_directory,
        problem_builder,
    )


__all__ = [
    "build_mh_config",
    "build_mh_run_config",
    "execute_mh_run",
    "run_mh_calibration",
]
