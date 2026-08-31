# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Shared workflow services for multi-chain Metropolis--Hastings runs.

The inference engine deliberately knows nothing about workflow result paths.
This module is the integration boundary: it translates validated YAML, gives
every stage a fresh :class:`~pyages.calibration.problem.CalibrationProblem`,
serializes the complete audit trail, and enforces the qualification policy.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.ensemble import MultiChainMetropolisHastings
from pyages.calibration.methods.mh.ensemble_config import (
    MHDiagnosticsConfig,
    MHEnsembleConfig,
    MHInitializationConfig,
    MHPilotConfig,
)
from pyages.calibration.methods.mh.errors import MHConvergenceError
from pyages.calibration.problem import CalibrationProblem
from pyages.config.models import MHMultichainCfg
from pyages.data_io.mh_results import write_mh_ensemble_result
from pyages.lpm.samples import LpmSampleTable

_ProblemBuilder = Callable[[Path], CalibrationProblem]


def _build_mh_ensemble_config(config: MHMultichainCfg) -> MHEnsembleConfig:
    """Return immutable scientific controls from a validated YAML section."""
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
        nstep=config.pilot.nstep,
        burn_in=config.pilot.burn_in,
        covariance_mode=config.pilot.covariance_mode,
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
    return MHEnsembleConfig(
        chains=config.chains,
        master_seed=config.master_seed,
        initialization=initialization,
        pilot=pilot,
        diagnostics=diagnostics,
    )


def _mh_stage_directory(
    output_directory: str | Path,
    stage: str,
    chain_id: int,
) -> Path:
    """Return the stable audit directory for one ensemble-engine stage."""
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
    raise ValueError(f"unknown MH ensemble stage: {stage!r}")


def run_mh_ensemble(
    chain_config: MHConfig,
    multichain_config: MHMultichainCfg,
    output_directory: str | Path,
    problem_builder: _ProblemBuilder,
) -> LpmSampleTable:
    """Execute, persist, qualify, and finally pool one multi-chain run.

    Chain and diagnostic artifacts are written before a required convergence
    failure is raised. Consequently, a rejected run remains fully auditable
    while unqualified draws cannot silently become a posterior distribution.
    """
    if not multichain_config.enabled:
        raise ValueError("multichain_config must be enabled")
    if not callable(problem_builder):
        raise TypeError("problem_builder must be callable")

    root = Path(output_directory)
    ensemble_config = _build_mh_ensemble_config(multichain_config)
    ensemble = MultiChainMetropolisHastings(chain_config, ensemble_config)

    def problem_factory(stage: str, chain_id: int) -> CalibrationProblem:
        return problem_builder(_mh_stage_directory(root, stage, chain_id))

    record = ensemble.run(problem_factory)
    pooled = write_mh_ensemble_result(
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


__all__ = ["run_mh_ensemble"]
