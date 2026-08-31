# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

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

from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.diagnostics import (
    bulk_ess,
    mcse_mean,
    split_rhat,
    tail_ess,
)
from pyages.calibration.methods.mh.ensemble_config import (
    MHEnsembleConfig,
    build_seed_plan,
)
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
    MHEnsembleResult,
    MHParameterDiagnostics,
    MHPilotResult,
)
from pyages.calibration.methods.mh.sampler import MetropolisHastings
from pyages.calibration.problem import CalibrationProblem, CalibrationTargetSignature

ProblemFactory = Callable[[str, int], CalibrationProblem]


class MHConvergenceError(RuntimeError):
    """Raised when qualified posterior output is requested before convergence."""


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
    chains. ``monitor`` and ``display_traj`` are rejected because those
    one-chain trajectory facilities do not identify the chain that produced
    their transient output. Complete chain tables are returned for external
    trace plots. ``display_text`` remains available and logs one summary per
    sampler (including pilot samplers when enabled).
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
        split_draws = ensemble_config.chains * 2 * (retained_count // 2)
        maximum_ess = split_draws * math.log10(split_draws)
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
        problem_factory: ProblemFactory,
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
        problem_factory: ProblemFactory,
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
        pilot_control = self.ensemble_config.pilot
        pilot_configs = tuple(
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
        if any(config.retained_sample_count() < 2 for config in pilot_configs):
            raise ValueError(
                "pilot nstep and burn_in must retain at least two draws per chain"
            )

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

        covariance = pooled_within_chain_covariance(
            matrices,
            relative_ridge=pilot_control.relative_ridge,
        )
        multiplier = (
            automatic_proposal_multiplier(matrices[0].shape[1])
            if pilot_control.proposal_multiplier is None
            else pilot_control.proposal_multiplier
        )
        result = MHPilotResult(
            final_states=tuple(final_states),
            covariance=covariance,
            proposal_multiplier=multiplier,
            acceptance_rates=tuple(acceptance_rates),
            retained_counts=tuple(len(matrix) for matrix in matrices),
            samples=tuple(matrices) if pilot_control.save_samples else None,
            initial_states=starts,
            runtime_seconds=tuple(runtimes),
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
        first = chains[0].samples
        parameter_names = first.get_param_names()
        names = list(dict.fromkeys(parameter_names + first.lpm_template.moments_name()))
        draw_counts = {len(chain.samples.frame) for chain in chains}
        if len(draw_counts) != 1:
            raise ValueError("production chains must retain the same number of draws")
        draw_count = next(iter(draw_counts))
        if draw_count < 8:
            raise ValueError(
                "production chains must retain at least eight draws for split "
                "rank-normalized diagnostics"
            )

        thresholds = self.ensemble_config.diagnostics
        diagnostics: list[MHParameterDiagnostics] = []
        for name in names:
            if any(name not in chain.samples.frame for chain in chains):
                raise ValueError(f"production samples are missing diagnostic {name!r}")
            values = np.vstack(
                [chain.samples.frame[name].to_numpy(dtype=float) for chain in chains]
            )
            is_constant_derived = name not in parameter_names and not np.any(
                values != values.flat[0]
            )
            rhat = split_rhat(values)
            bulk = bulk_ess(values)
            tail = tail_ess(values)
            try:
                monte_carlo_error = mcse_mean(values)
            except ValueError:
                monte_carlo_error = math.inf
            posterior_sd = float(np.std(values, ddof=1))
            qualified = bool(
                math.isfinite(rhat)
                and rhat < thresholds.max_rhat
                and bulk >= thresholds.min_bulk_ess
                and tail >= thresholds.min_tail_ess
                and math.isfinite(monte_carlo_error)
            )
            diagnostics.append(
                MHParameterDiagnostics(
                    parameter=name,
                    rhat=rhat,
                    bulk_ess=bulk,
                    tail_ess=tail,
                    mcse_mean=monte_carlo_error,
                    posterior_sd=posterior_sd,
                    qualified=qualified,
                    included_in_qualification=not is_constant_derived,
                )
            )
        return tuple(diagnostics)

    def run(self, problem_factory: ProblemFactory) -> MHEnsembleResult:
        """Run initialization, optional pilot, production, and diagnostics.

        Parameters
        ----------
        problem_factory : callable
            ``problem_factory(stage, chain_id)`` must create and prepare a new
            :class:`CalibrationProblem` for each invocation. ``stage`` is one
            of ``"initialization"``, ``"pilot"``, or ``"production"``.

        Returns
        -------
        MHEnsembleResult
            Separate production chains, optional pilot provenance, convergence
            metrics, and the resulting qualification status.
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
            tuple(
                self._fresh_problem(
                    problem_factory,
                    "pilot",
                    chain_id,
                    seen_problems,
                    target_signature,
                )
                for chain_id in range(1, self.ensemble_config.chains + 1)
            )
            if self.ensemble_config.pilot.enabled
            else ()
        )
        production_problems = tuple(
            self._fresh_problem(
                problem_factory,
                "production",
                chain_id,
                seen_problems,
                target_signature,
            )
            for chain_id in range(1, self.ensemble_config.chains + 1)
        )
        pilot = None
        pilot_proposal_metadata: dict[str, Any] = {}
        pilot_prior_metadata: dict[str, Any] = {}
        production_starts = starts
        if self.ensemble_config.pilot.enabled:
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
        resolved_metadata: dict[str, Any] = {}
        if pilot is None:
            resolved_metadata.update(production_proposal_metadata)
        else:
            resolved_metadata.update(
                {
                    f"pilot_{name}": value
                    for name, value in pilot_proposal_metadata.items()
                }
            )
        resolved_metadata.update(production_prior_metadata)
        diagnostics_message = None
        try:
            diagnostics = self._diagnose(chains)
        except (FloatingPointError, ValueError) as exc:
            diagnostics = ()
            diagnostics_message = str(exc)
            status = DIAGNOSTICS_UNAVAILABLE
        else:
            status = (
                QUALIFIED
                if all(
                    item.qualified
                    for item in diagnostics
                    if item.included_in_qualification
                )
                else NOT_QUALIFIED
            )
        return MHEnsembleResult(
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
    "MHConvergenceError",
    "MultiChainMetropolisHastings",
    "ProblemFactory",
]
