# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file translates validated workflow settings into single- or multi-chain
# Metropolis--Hastings runs and creates a fresh calibration problem per stage.

"""Shared workflow services for Metropolis--Hastings runs.

The inference engine deliberately knows nothing about workflow result paths.
This module is the integration boundary: it translates validated YAML, gives
every stage a fresh :class:`~pyages.calibration.problem.CalibrationProblem`,
handles the single/ensemble branch, serializes the audit trail, and enforces the
qualification policy.
"""

from __future__ import annotations

import secrets
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
from pyages.calibration.methods.mh.sampler import MetropolisHastings
from pyages.calibration.problem import CalibrationProblem
from pyages.config.models import (
    LauncherMetropolisCfg,
    MHMultichainCfg,
    TemporalCalibrationCfg,
)
from pyages.data_io.mh_results import (
    clear_mh_ensemble_artifacts,
    write_mh_ensemble_result,
)
from pyages.lpm.samples import LpmSampleTable

_ProblemBuilder = Callable[[Path], CalibrationProblem]


def build_mh_config(
    config: LauncherMetropolisCfg | TemporalCalibrationCfg,
) -> MHConfig:
    """Translate either workflow's validated settings into one chain config."""
    if isinstance(config, LauncherMetropolisCfg):
        return MHConfig(
            nstep=config.nstep,
            burn_in=config.burn_in,
            nskip=config.nskip,
            prior_option=config.prior_option,
            likelihood=config.likelihood,
            monitor=config.monitor,
            display_traj=config.display_traj,
            componentwise_source="model",
            seed=config.seed,
        )
    if isinstance(config, TemporalCalibrationCfg):
        multichain_enabled = config.multichain is not None and config.multichain.enabled
        seed = (
            0
            if multichain_enabled
            else config.seed
            if config.seed_enabled
            else secrets.randbits(63)
        )
        if seed is None:
            raise ValueError("calibration.seed is required when seed_enabled is true")
        return MHConfig(
            nstep=config.mh_nsteps,
            burn_in=config.burn_in,
            nskip=config.nskip,
            prior_option=True,
            prior_type="parametric",
            likelihood=True,
            monitor=False,
            display_traj=False,
            display_text=False,
            componentwise_source="model",
            seed=seed,
        )
    raise TypeError("config must be a validated single-date or temporal MH config")


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


def run_mh_calibration(
    chain_config: MHConfig,
    multichain_config: MHMultichainCfg | None,
    output_directory: str | Path,
    problem_builder: _ProblemBuilder,
) -> LpmSampleTable:
    """Run one chain or a qualified ensemble behind one workflow boundary."""
    root = Path(output_directory)
    if multichain_config is not None and multichain_config.enabled:
        return run_mh_ensemble(
            chain_config,
            multichain_config,
            root,
            problem_builder,
        )

    clear_mh_ensemble_artifacts(root)
    calibration = MetropolisHastings(config=chain_config)
    results = calibration.run(problem_builder(root))
    calibration.write_calibrated_lpm(results)
    return results


__all__ = ["build_mh_config", "run_mh_calibration", "run_mh_ensemble"]
