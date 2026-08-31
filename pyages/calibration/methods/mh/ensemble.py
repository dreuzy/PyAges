# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# Purpose: Orchestrate MH initialization, pilot, production, and diagnostics.

"""Orchestration of independent Metropolis--Hastings chain ensembles.

Pilot chains and production chains deliberately use distinct random streams
and distinct :class:`~pyages.calibration.problem.CalibrationProblem` objects.

The pilot is adaptation *between* Markov chains: it learns one covariance,
which is then frozen for every production transition.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from weakref import WeakSet

import numpy as np

from pyages.calibration.methods.mh._diagnostic_contract import (
    build_diagnostic_quantities,
)
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.diagnostics import (
    bulk_ess,
    ess,
    mcse_mean,
    split_rhat,
    tail_ess,
)
from pyages.calibration.methods.mh.ensemble_config import (
    MHEnsembleConfig,
    build_seed_plan,
)
from pyages.calibration.methods.mh.errors import MHDiagnosticsUnavailableError
from pyages.calibration.methods.mh.initialization import build_initial_states
from pyages.calibration.methods.mh.pilot import (
    automatic_proposal_multiplier,
    pooled_within_chain_covariance,
)
from pyages.calibration.methods.mh.prior import Prior
from pyages.calibration.methods.mh.results import (
    DIAGNOSTICS_UNAVAILABLE,
    NOT_QUALIFIED,
    QUALIFIED,
    MHChainResult,
    MHParameterDiagnostics,
    MHPilotResult,
    MHRunRecord,
)
from pyages.calibration.methods.mh.sampler import MetropolisHastings
from pyages.calibration.problem import CalibrationProblem
from pyages.calibration.sampling_schedule import maximum_split_ess
from pyages.calibration.target_signature import CalibrationTargetSignature

_ProblemFactory = Callable[[str, int], CalibrationProblem]


class MultiChainMetropolisHastings:
    """Run pilot and production MH chains with auditable random streams.

    Parameters
    ----------
    chain_config : MHConfig
        Scientific controls for each production chain. The ensemble always
        supplies ``seed`` and ``initial_params``. With a pilot, this config
        must request the componentwise kernel used for adaptation; production
        then uses the learned covariance as one frozen correlated kernel.
    ensemble_config : pyages.calibration.methods.mh.ensemble_config.MHEnsembleConfig
        Chain count, initialization, optional pilot, and qualification rules.

    Notes
    -----
    ``problem_factory(stage, chain_id)`` passed to :meth:`run` must return a
    freshly prepared problem. Reusing a problem is rejected because objective
    evaluation mutates the LPM state and would couple otherwise independent
    chains.

    ``monitor`` and ``display_traj`` are rejected because those one-chain
    trajectory facilities do not identify the chain that produced their
    transient output. Complete chain tables are returned for external trace
    plots.

    ``display_text`` remains available and logs one summary per sampler,
    including pilot samplers when enabled.

    """

    def __init__(
        self,
        chain_config: MHConfig,
        ensemble_config: MHEnsembleConfig,
    ) -> None:
        """Store validated immutable chain and ensemble configurations."""
        if not isinstance(chain_config, MHConfig):
            raise TypeError("chain_config must be an MHConfig")
        if not isinstance(ensemble_config, MHEnsembleConfig):
            raise TypeError("ensemble_config must be an MHEnsembleConfig")
        if chain_config.monitor or chain_config.display_traj:
            raise ValueError(
                "monitor and display_traj are one-chain options; use the saved "
                "per-chain tables for multi-chain trace diagnostics"
            )
        if (
            ensemble_config.pilot.enabled
            and chain_config.proposal_kind != "componentwise"
        ):
            raise ValueError(
                "pilot-enabled multi-chain MH requires "
                "proposal_kind='componentwise'; the pilot learns the correlated "
                "production covariance"
            )
        retained_count = chain_config.retained_sample_count()
        if retained_count < 8:
            raise ValueError(
                "each production chain must retain at least eight draws for "
                "multi-chain diagnostics"
            )
        maximum_ess = maximum_split_ess(ensemble_config.chains, retained_count)
        diagnostics = ensemble_config.diagnostics
        if diagnostics.require_convergence and (
            diagnostics.min_bulk_ess > maximum_ess
            or diagnostics.min_tail_ess > maximum_ess
        ):
            raise ValueError(
                "diagnostic ESS thresholds exceed the maximum split-draw ESS "
                f"of {maximum_ess:.6g}; retain more production draws or disable "
                "required convergence for an exploratory run"
            )
        self.chain_config = chain_config
        self.ensemble_config = ensemble_config

    @staticmethod
    def _fresh_problem(
        problem_factory: _ProblemFactory,
        stage: str,
        chain_id: int,
        seen_problems: WeakSet[CalibrationProblem],
        expected_target: CalibrationTargetSignature | None = None,
    ) -> CalibrationProblem:
        """Build and validate one fresh, scientifically identical problem."""
        problem = problem_factory(stage, chain_id)
        if not isinstance(problem, CalibrationProblem):
            raise TypeError("problem_factory must return CalibrationProblem objects")
        problem.ensure_prepared()
        if problem in seen_problems:
            raise ValueError(
                "problem_factory must return a fresh CalibrationProblem for "
                "every pilot and production chain"
            )
        seen_problems.add(problem)
        if expected_target is not None:
            actual_target = problem.target_signature()
            category = expected_target.differing_category(actual_target)
            if category is not None:
                raise ValueError(
                    "problem_factory returned an inconsistent scientific target: "
                    f"stage={stage!r}, chain_id={chain_id}, category={category!r}"
                )
        return problem

    @staticmethod
    def _common_metadata(
        snapshots: list[dict[str, Any]],
        *,
        stage: str,
        category: str,
    ) -> dict[str, Any]:
        """Return identical per-chain metadata or reject source drift."""
        if not snapshots:
            raise AssertionError(f"{stage} produced no {category} metadata")
        reference = snapshots[0]
        if any(snapshot != reference for snapshot in snapshots[1:]):
            raise ValueError(
                f"resolved {category} metadata changed between {stage} chains"
            )
        return dict(reference)

    def _initial_states(
        self,
        problem_factory: _ProblemFactory,
        initialization_seeds: tuple[int, ...],
        seen_problems: WeakSet[CalibrationProblem],
    ) -> tuple[
        tuple[dict[str, float], ...],
        dict[str, Any],
        CalibrationTargetSignature,
    ]:
        """Construct independent starts from a prepared prototype model."""
        prototype = self._fresh_problem(
            problem_factory, "initialization", 0, seen_problems
        )
        if prototype.lpm is None:  # narrowed by ``ensure_prepared``
            raise AssertionError("prepared problem has no LPM")
        prior = Prior(
            option=self.chain_config.prior_option,
            typ=self.chain_config.prior_type,
            prior_file=self.chain_config.prior_file,
        )
        if (
            self.chain_config.prior_option
            or self.ensemble_config.initialization.strategy.startswith("prior_")
        ):
            prior.load(prototype.lpm)
        states = build_initial_states(
            prototype.lpm,
            prior,
            self.ensemble_config.initialization,
            self.ensemble_config.chains,
            initialization_seeds,
        )
        return (
            states,
            prior.resolved_metadata(prototype.lpm),
            prototype.target_signature(),
        )

    def _run_pilot(
        self,
        problems: tuple[CalibrationProblem, ...],
        starts: tuple[dict[str, float], ...],
        seeds: tuple[int, ...],
        expected_prior_metadata: dict[str, Any],
    ) -> tuple[MHPilotResult, dict[str, Any], dict[str, Any]]:
        """Learn one fixed native-coordinate covariance from pilot chains."""
        pilot_configs = self._pilot_configs(starts, seeds)

        matrices: list[np.ndarray] = []
        final_states: list[dict[str, float]] = []
        acceptance_rates: list[float] = []
        runtimes: list[float] = []
        proposal_snapshots: list[dict[str, Any]] = []
        prior_snapshots: list[dict[str, Any]] = []
        for problem, config in zip(problems, pilot_configs, strict=True):
            sampler = MetropolisHastings(config)
            sampler.expect_resolved_metadata(
                proposal=(proposal_snapshots[0] if proposal_snapshots else None),
                prior=expected_prior_metadata,
            )
            samples = sampler.run(problem)
            names = samples.get_param_names()
            matrix = samples.frame[names].to_numpy(dtype=float, copy=True)
            matrices.append(matrix)
            final_states.append(
                {name: float(matrix[-1, index]) for index, name in enumerate(names)}
            )
            acceptance_rates.append(sampler.success_rate)
            runtimes.append(float(sampler.time_perform))
            proposal_snapshots.append(sampler.resolved_proposal_metadata)
            prior_snapshots.append(sampler.resolved_prior_metadata)

        result = self._pilot_result(
            matrices=matrices,
            final_states=final_states,
            acceptance_rates=acceptance_rates,
            runtimes=runtimes,
            starts=starts,
        )
        return (
            result,
            self._common_metadata(
                proposal_snapshots,
                stage="pilot",
                category="proposal",
            ),
            self._common_metadata(
                prior_snapshots,
                stage="pilot",
                category="prior",
            ),
        )

    def _pilot_configs(
        self,
        starts: tuple[dict[str, float], ...],
        seeds: tuple[int, ...],
    ) -> tuple[MHConfig, ...]:
        """Build componentwise pilot configs on their independent streams."""
        pilot_control = self.ensemble_config.pilot
        configs = tuple(
            replace(
                self.chain_config,
                nstep=pilot_control.nstep,
                burn_in=pilot_control.burn_in,
                nskip=1,
                seed=seed,
                initial_params=dict(start),
                monitor=False,
                display_traj=False,
                proposal_kind="componentwise",
                proposal_scales=None,
                proposal_covariance=None,
                proposal_multiplier=1.0,
            )
            for start, seed in zip(starts, seeds, strict=True)
        )
        if any(config.retained_sample_count() < 2 for config in configs):
            raise ValueError(
                "pilot nstep and burn_in must retain at least two draws per chain"
            )
        return configs

    def _pilot_result(
        self,
        *,
        matrices: list[np.ndarray],
        final_states: list[dict[str, float]],
        acceptance_rates: list[float],
        runtimes: list[float],
        starts: tuple[dict[str, float], ...],
    ) -> MHPilotResult:
        """Freeze learned pilot adaptation and its complete provenance."""
        pilot_control = self.ensemble_config.pilot
        covariance = pooled_within_chain_covariance(
            matrices,
            relative_ridge=pilot_control.relative_ridge,
        )
        multiplier = (
            automatic_proposal_multiplier(matrices[0].shape[1])
            if pilot_control.proposal_multiplier is None
            else pilot_control.proposal_multiplier
        )
        return MHPilotResult(
            final_states=tuple(final_states),
            covariance=covariance,
            proposal_multiplier=multiplier,
            acceptance_rates=tuple(acceptance_rates),
            retained_counts=tuple(len(matrix) for matrix in matrices),
            samples=tuple(matrices) if pilot_control.save_samples else None,
            initial_states=starts,
            runtime_seconds=tuple(runtimes),
        )

    def _production_config(
        self,
        *,
        initial_params: dict[str, float],
        seed: int,
        pilot: MHPilotResult | None,
    ) -> MHConfig:
        """Return one production configuration with a fixed proposal kernel."""
        replacements: dict[str, object] = {
            "seed": seed,
            "initial_params": dict(initial_params),
            "monitor": False,
            "display_traj": False,
        }
        if pilot is not None:
            replacements.update(
                proposal_kind="correlated",
                proposal_scales=None,
                proposal_covariance=tuple(
                    tuple(float(value) for value in row) for row in pilot.covariance
                ),
                proposal_multiplier=pilot.proposal_multiplier,
            )
        return replace(self.chain_config, **replacements)

    def _run_production(
        self,
        problems: tuple[CalibrationProblem, ...],
        starts: tuple[dict[str, float], ...],
        seeds: tuple[int, ...],
        pilot: MHPilotResult | None,
        expected_prior_metadata: dict[str, Any],
    ) -> tuple[
        tuple[MHChainResult, ...],
        dict[str, Any],
        dict[str, Any],
    ]:
        """Run every independent production chain without pooling its draws."""
        results: list[MHChainResult] = []
        proposal_snapshots: list[dict[str, Any]] = []
        prior_snapshots: list[dict[str, Any]] = []
        for chain_id, (problem, start, seed) in enumerate(
            zip(problems, starts, seeds, strict=True), start=1
        ):
            config = self._production_config(
                initial_params=start,
                seed=seed,
                pilot=pilot,
            )
            sampler = MetropolisHastings(config)
            sampler.expect_resolved_metadata(
                proposal=(proposal_snapshots[0] if proposal_snapshots else None),
                prior=expected_prior_metadata,
            )
            samples = sampler.run(problem)
            proposal_snapshots.append(sampler.resolved_proposal_metadata)
            prior_snapshots.append(sampler.resolved_prior_metadata)
            results.append(
                MHChainResult(
                    chain_id=chain_id,
                    seed=seed,
                    initial_params=start,
                    samples=samples,
                    acceptance_rate=sampler.success_rate,
                    runtime_seconds=float(sampler.time_perform),
                )
            )
        return (
            tuple(results),
            self._common_metadata(
                proposal_snapshots,
                stage="production",
                category="proposal",
            ),
            self._common_metadata(
                prior_snapshots,
                stage="production",
                category="prior",
            ),
        )

    def _diagnose(
        self, chains: tuple[MHChainResult, ...]
    ) -> tuple[MHParameterDiagnostics, ...]:
        """Calculate diagnostics before any production-chain pooling."""
        quantities = build_diagnostic_quantities(
            tuple(chain.samples for chain in chains)
        )
        draw_count = quantities[0].values.shape[1]
        if draw_count < 8:
            raise ValueError(
                "production chains must retain at least eight draws for split "
                "rank-normalized diagnostics"
            )

        thresholds = self.ensemble_config.diagnostics
        diagnostics: list[MHParameterDiagnostics] = []
        for quantity in quantities:
            name = quantity.name
            values = quantity.values
            if not np.all(np.isfinite(values)):
                raise MHDiagnosticsUnavailableError(
                    f"diagnostic {name!r} contains non-finite production values"
                )
            try:
                rhat = split_rhat(values)
                bulk = bulk_ess(values)
                tail = tail_ess(values)
            except FloatingPointError as exc:
                raise MHDiagnosticsUnavailableError(
                    f"diagnostic {name!r} could not be evaluated"
                ) from exc
            raw_ess = ess(values)
            monte_carlo_error = (
                mcse_mean(values, effective_sample_size=raw_ess)
                if math.isfinite(raw_ess) and raw_ess > 0.0
                else math.inf
            )
            posterior_sd = float(np.std(values, ddof=1))
            diagnostics.append(
                MHParameterDiagnostics.from_metrics(
                    parameter=name,
                    rhat=rhat,
                    bulk_ess=bulk,
                    tail_ess=tail,
                    mcse_mean=monte_carlo_error,
                    posterior_sd=posterior_sd,
                    thresholds=thresholds,
                    included_in_qualification=quantity.included_in_qualification,
                )
            )
        return tuple(diagnostics)

    def _stage_problems(
        self,
        problem_factory: _ProblemFactory,
        stage: str,
        seen_problems: WeakSet[CalibrationProblem],
        target_signature: CalibrationTargetSignature,
    ) -> tuple[CalibrationProblem, ...]:
        """Create all scientifically identical problems for one chain phase."""
        return tuple(
            self._fresh_problem(
                problem_factory,
                stage,
                chain_id,
                seen_problems,
                target_signature,
            )
            for chain_id in range(1, self.ensemble_config.chains + 1)
        )

    @staticmethod
    def _resolved_metadata(
        pilot: MHPilotResult | None,
        pilot_proposal: dict[str, Any],
        production_proposal: dict[str, Any],
        production_prior: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine phase metadata under the persisted naming convention."""
        metadata: dict[str, Any] = {}
        if pilot is None:
            metadata.update(production_proposal)
        else:
            metadata.update(
                {f"pilot_{name}": value for name, value in pilot_proposal.items()}
            )
        metadata.update(production_prior)
        return metadata

    def _diagnostic_outcome(
        self,
        chains: tuple[MHChainResult, ...],
    ) -> tuple[
        tuple[MHParameterDiagnostics, ...],
        str,
        str | None,
    ]:
        """Return complete diagnostics, qualification status, and failure detail."""
        try:
            diagnostics = self._diagnose(chains)
        except MHDiagnosticsUnavailableError as exc:
            return (), DIAGNOSTICS_UNAVAILABLE, str(exc)
        status = (
            QUALIFIED
            if all(
                item.qualified for item in diagnostics if item.included_in_qualification
            )
            else NOT_QUALIFIED
        )
        return diagnostics, status, None

    def run(self, problem_factory: _ProblemFactory) -> MHRunRecord:
        """Run initialization, optional pilot, production, and diagnostics.

        Parameters
        ----------
        problem_factory : callable
            ``problem_factory(stage, chain_id)`` must create and prepare a new
            :class:`CalibrationProblem` for each invocation.

            ``stage`` is one of ``"initialization"``, ``"pilot"``, or
            ``"production"``.

        Returns
        -------
        MHRunRecord
            Immutable configuration, separate production chains, optional pilot
            provenance, convergence metrics, and qualification status.

        """
        if not callable(problem_factory):
            raise TypeError("problem_factory must be callable")
        seen_problems: WeakSet[CalibrationProblem] = WeakSet()
        seeds = build_seed_plan(self.ensemble_config)
        (
            starts,
            initialization_prior_metadata,
            target_signature,
        ) = self._initial_states(
            problem_factory,
            seeds.initialization_seeds,
            seen_problems,
        )
        pilot_problems = (
            self._stage_problems(
                problem_factory,
                "pilot",
                seen_problems,
                target_signature,
            )
            if self.ensemble_config.pilot.enabled
            else ()
        )
        production_problems = self._stage_problems(
            problem_factory,
            "production",
            seen_problems,
            target_signature,
        )

        pilot = None
        pilot_proposal_metadata: dict[str, Any] = {}
        pilot_prior_metadata: dict[str, Any] = {}
        production_starts = starts
        if pilot_problems:
            (
                pilot,
                pilot_proposal_metadata,
                pilot_prior_metadata,
            ) = self._run_pilot(
                pilot_problems,
                starts,
                seeds.pilot_seeds,
                initialization_prior_metadata,
            )
            production_starts = pilot.final_states

        (
            chains,
            production_proposal_metadata,
            production_prior_metadata,
        ) = self._run_production(
            production_problems,
            production_starts,
            seeds.production_seeds,
            pilot,
            initialization_prior_metadata,
        )
        if pilot is not None and pilot_prior_metadata != production_prior_metadata:
            raise ValueError(
                "resolved prior metadata changed between pilot and production"
            )
        diagnostics, status, diagnostics_message = self._diagnostic_outcome(chains)
        resolved_metadata = self._resolved_metadata(
            pilot,
            pilot_proposal_metadata,
            production_proposal_metadata,
            production_prior_metadata,
        )
        return MHRunRecord(
            chain_config=self.chain_config,
            ensemble_config=self.ensemble_config,
            chains=chains,
            pilot=pilot,
            diagnostics=diagnostics,
            qualification_status=status,
            seed_plan=seeds,
            target_signature_version=target_signature.version,
            target_sha256=target_signature.sha256,
            diagnostics_message=diagnostics_message,
            resolved_metadata=resolved_metadata,
        )


__all__ = [
    "MultiChainMetropolisHastings",
]
