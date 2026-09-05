# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file runs one MH chain from its initial state to its retained samples.

"""Run one Metropolis--Hastings chain for a lumped-parameter model.

The sampler prepares the prior and proposal, evaluates the starting state,
performs the configured number of accept-or-reject transitions, and stores the
states selected by the burn-in and thinning schedule. A rejected proposal
keeps the current state, so repeated rows are expected and must remain in the
saved Markov chain.

For each retained state, the result table stores model parameters, modeled
concentrations, and ``obj_function``. That column is a normalized residual
measure, not the posterior log-density used in the acceptance decision.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from pyages.calibration.methods.base import CalibrationMethod
from pyages.calibration.methods.mh._sampler_target import MHTarget
from pyages.calibration.methods.mh.config import MHConfig
from pyages.calibration.methods.mh.prior import Prior
from pyages.calibration.methods.mh.proposals import (
    ComponentwiseRandomWalk,
    GaussianRandomWalk,
    Proposal,
)
from pyages.calibration.methods.mh.trajectory import MHTrajectory
from pyages.calibration.objective import normalized_residual_norm
from pyages.calibration.outputs import write_key_values
from pyages.lpm.samples.table import LpmSampleTable

logger = logging.getLogger(__name__)

__all__ = ["MetropolisHastings"]


@dataclass(frozen=True, slots=True)
class _MHState:
    """Values that must move together when a proposal is accepted."""

    params: list[float]
    log_posterior: float
    chi_square: float
    concentrations: list[float]


class MetropolisHastings(CalibrationMethod):
    r"""Sample an LPM posterior with a Metropolis-Hastings chain.

    For parameters :math:`\theta` within the configured calibration ranges, the target
    log density is

    .. math::

       \log\pi(\theta)=-\tfrac12\chi^2(\theta)+\log p(\theta)+c,

    with omitted terms disabled by ``MHConfig.likelihood`` and
    ``MHConfig.prior_option``. Observation errors are treated as independent
    known Gaussian standard deviations. A proposal :math:`\theta'` is accepted
    using

    .. math::

       \log u < \log\pi(\theta')-\log\pi(\theta)
       +\log q(\theta\mid\theta')-\log q(\theta'\mid\theta).

    Native and sum/difference Gaussian random walks have zero Hastings term;
    the SciPy inverse-Gaussian coordinate proposal includes its Jacobian.
    Out-of-range proposals and zero-support prior values have log target
    ``-inf`` and are rejected.

    The immutable :class:`MHConfig` controls sampling, prior, proposal, random
    seed, and monitoring. :meth:`perform` stores the current state after
    burn-in/thinning, including repeated states following rejected proposals.

    Notes
    -----
    ``obj_function`` in returned tables is :math:`\sqrt{\chi^2/n}`, not the log
    target used for acceptance. The algorithm does not by itself certify
    convergence; publication runs require multiple-chain diagnostics. See
    ``docs/scientific-methods.md`` and
    ``docs/reports/mh_proposal_qualification.md``.

    """

    def __init__(self, config: MHConfig) -> None:
        """Initialize the sampler from one immutable scientific configuration."""
        super().__init__()
        # Immutable controls and proposal-step policy are resolved once per run.
        self.method = "Metropolis_Hastings"
        if not isinstance(config, MHConfig):
            raise TypeError("config must be an MHConfig instance")
        self.config = config
        # Prior definitions are loaded only after a concrete LPM is bound.
        self.prior = Prior(
            option=self.config.prior_option,
            typ=self.config.prior_type,
            prior_file=self.config.prior_file,
        )
        # Run diagnostics are reset here and populated by ``perform``.
        self._success_rate = 0.0
        self._initial_params_used: dict[str, float] = {}
        self._initialization_source = ""
        self.prior_validation_stats = None
        self.trajectory: MHTrajectory | None = None
        self.time_perform = 0
        self._proposal: Proposal | None = None
        self._target: MHTarget | None = None
        self._resolved_proposal_metadata: dict[str, Any] = {}
        self._resolved_prior_metadata: dict[str, Any] = {}
        self._expected_proposal_metadata: dict[str, Any] | None = None
        self._expected_prior_metadata: dict[str, Any] | None = None

    def _draw_proposal(self, p0: list[float], rng: np.random.Generator) -> list[float]:
        """Draw one unbounded proposal from the configured random walk."""
        if self._proposal is None:
            raise RuntimeError("Proposal must be prepared before drawing")
        return self._proposal.draw(p0, rng).tolist()

    def _prepare_proposal(self) -> None:
        """Resolve one proposal implementation after model setup.

        Componentwise proposals retain their scalar-draw implementation for
        seeded reproducibility.  Other modes construct one immutable covariance
        in the declared coordinate system.  ``proposal_multiplier`` scales
        standard deviations, hence covariance is multiplied by its square.
        """
        kind = self.config.proposal_kind
        if kind == "componentwise":
            proposal = ComponentwiseRandomWalk(
                self.config.componentwise_source,
                self.config.componentwise_fraction,
            )
            proposal.prepare(self.lpm)
            self._proposal = proposal
            return
        dimension = len(self.lpm.p)
        multiplier = float(self.config.proposal_multiplier)
        if not math.isfinite(multiplier) or multiplier <= 0.0:
            raise ValueError("proposal_multiplier must be finite and positive")
        if kind in {"diagonal", "sum_difference"}:
            if self.config.proposal_scales is None:
                raise ValueError(f"{kind} requires proposal_scales")
            if len(self.config.proposal_scales) != dimension:
                raise ValueError("proposal_scales dimension does not match the LPM")
            coordinate_system = (
                "sum_difference" if kind == "sum_difference" else "native"
            )
            self._proposal = GaussianRandomWalk.diagonal(
                np.asarray(self.config.proposal_scales, dtype=float) * multiplier,
                coordinate_system=coordinate_system,
            )
            return
        if kind in {"correlated", "scipy_ig_correlated"}:
            if self.config.proposal_covariance is None:
                raise ValueError("correlated requires proposal_covariance")
            covariance = np.asarray(self.config.proposal_covariance, dtype=float)
            if covariance.shape != (dimension, dimension):
                raise ValueError("proposal_covariance dimension does not match the LPM")
            coordinate_system = (
                "scipy_ig" if kind == "scipy_ig_correlated" else "native"
            )
            self._proposal = GaussianRandomWalk(
                covariance * multiplier**2, coordinate_system=coordinate_system
            )
            return
        raise ValueError(f"Unknown proposal_kind: {kind!r}")

    def _capture_resolved_metadata(self) -> None:
        """Snapshot prepared proposal and prior inputs before transitions.

        Some settings are resolved from mutable files only after an LPM has
        been bound.  Capturing their effective values here makes later output
        independent of any file changes during or after the chain.
        """
        proposal_metadata: dict[str, Any] = {}
        if isinstance(self._proposal, ComponentwiseRandomWalk):
            self._proposal.add_metadata(proposal_metadata)
        prior_metadata = self.prior.resolved_metadata(self.lpm)

        self._resolved_proposal_metadata = deepcopy(proposal_metadata)
        self._resolved_prior_metadata = deepcopy(prior_metadata)
        if (
            self._expected_proposal_metadata is not None
            and self._resolved_proposal_metadata != self._expected_proposal_metadata
        ):
            raise ValueError(
                "resolved proposal metadata changed since the reference snapshot"
            )
        if (
            self._expected_prior_metadata is not None
            and self._resolved_prior_metadata != self._expected_prior_metadata
        ):
            raise ValueError("resolved prior metadata changed since initialization")

    def expect_resolved_metadata(
        self,
        *,
        proposal: Mapping[str, Any] | None = None,
        prior: Mapping[str, Any] | None = None,
    ) -> None:
        """Set optional snapshots that preparation must reproduce exactly."""
        if self._proposal is not None:
            raise RuntimeError("expected metadata must be set before sampler.run()")
        self._expected_proposal_metadata = (
            None if proposal is None else deepcopy(dict(proposal))
        )
        self._expected_prior_metadata = None if prior is None else deepcopy(dict(prior))

    @property
    def resolved_proposal_metadata(self) -> dict[str, Any]:
        """Return a detached snapshot of the proposal used by this chain."""
        return deepcopy(self._resolved_proposal_metadata)

    @property
    def resolved_prior_metadata(self) -> dict[str, Any]:
        """Return a detached snapshot of the prior used by this chain."""
        return deepcopy(self._resolved_prior_metadata)

    def _log_posterior_eval(
        self,
        params: list[float],
        data_conc: np.ndarray,
        data_error: np.ndarray,
    ) -> tuple[float, float, list[float]]:
        r"""Evaluate ``-chi_square/2 + log(prior)`` in log space.

        The normalization constants of the independent Gaussian likelihood do
        not depend on LPM parameters and are omitted. Log space prevents
        underflow. Calibration ranges and prior supports preserve exact zero
        density outside their configured domains.
        """
        if self._target is None:
            raise RuntimeError("MH target must be prepared before evaluation")
        return self._target.evaluate(params, data_conc, data_error)

    def _should_retain(self, iteration: int) -> bool:
        """Return whether one zero-based MCMC iteration must be stored."""
        return self.config.should_retain(iteration)

    def _prepare_storage(self) -> tuple[np.ndarray, list[str]]:
        """Preallocate the exact retained-row matrix and its canonical columns.

        Preallocation keeps allocation out of the transition loop.  Every row
        contains native LPM parameters, the dimensionless residual diagnostic,
        modeled observations in canonical order, and the bounds flag expected
        by :class:`~pyages.lpm.samples.table.LpmSampleTable`.
        """
        column_names = (
            self.lpm.get_param_names()
            + ["obj_function"]
            + list(self.observations.observation_keys())
            + ["param_in_bounds"]
        )
        return (
            np.zeros(
                (self.config.retained_sample_count(), len(column_names)),
                dtype=float,
            ),
            column_names,
        )

    def _mcmc_step(
        self,
        current: _MHState,
        data_conc: np.ndarray,
        data_error: np.ndarray,
        rng: np.random.Generator,
    ) -> tuple[_MHState, bool]:
        r"""Perform one Metropolis-Hastings transition.

        Acceptance compares ``log(u)`` with the proposed-minus-current log
        target plus ``log q(current|proposed) - log q(proposed|current)``.
        A rejected proposal returns the current parameters, objective, and
        concentrations unchanged, so downstream thinning retains repeated
        states as required for a Markov-chain sample.

        Returns
        -------
        tuple
            Updated params, log-posterior, objective function, concentrations,
            and a success flag.

        """
        # Draw in the selected coordinates, then evaluate the physical target.
        params_n = self._draw_proposal(current.params, rng)
        log_pn, chi_square_n, conc_n = self._log_posterior_eval(
            params_n, data_conc, data_error
        )
        # Symmetric proposals contribute zero; nonlinear coordinate proposals
        # supply log q(current|proposed) - log q(proposed|current).
        if self._proposal is None:
            raise RuntimeError("Proposal must be prepared before a transition")
        log_hastings = self._proposal.log_hastings_ratio(current.params, params_n)
        success = log_pn + log_hastings >= current.log_posterior
        if not success:
            log_acceptance = log_pn - current.log_posterior + log_hastings
            success = np.log(rng.random()) < log_acceptance
        if not success:
            return current, False

        # Commit only an accepted candidate to the public calibration LPM.
        self.lpm.set_param_from_array(params_n)
        return _MHState(params_n, log_pn, chi_square_n, conc_n), True

    def _finalize_trajectory(self, traj: MHTrajectory, n: int) -> None:
        """Resize and optionally display the retained trajectory."""
        traj.resize(n)
        if self.config.display_traj:
            traj.plot(self.display_options.directory)
        if self.config.display_text:
            logger.info(
                "MH retained trajectory summary:\n%s", traj.summary().to_string()
            )

    def _prepare_mcmc(
        self,
    ) -> tuple[
        np.random.Generator,
        np.ndarray,
        np.ndarray,
        MHTrajectory | None,
        np.ndarray,
        list[str],
    ]:
        """Prepare observations, prior, proposal, RNG, and result storage.

        This method performs every allocation and file-backed load that must
        stay outside the hot transition loop.  Observation arrays are captured
        once so their order cannot drift during sampling.
        """
        self._resolved_proposal_metadata = {}
        self._resolved_prior_metadata = {}
        self._target = None
        # Prior-only validation requires retained trajectory values.
        monitor = self.config.monitor or (
            self.config.likelihood is False and self.prior.option is True
        )
        rng = np.random.default_rng(self.config.seed)
        data_conc, data_error = self.observation_arrays()
        self._prepare_proposal()
        # Monitoring stores retained states only; it is not a second chain.
        traj = (
            MHTrajectory(self.lpm.p.keys(), self.config.retained_sample_count())
            if monitor
            else None
        )
        # Priors depend on the bound model's names and calibration ranges.
        self.prior.load(self.lpm)
        self._target = MHTarget(
            self.problem,
            self.prior,
            likelihood=self.config.likelihood,
        )
        self._capture_resolved_metadata()
        array_results, array_col_names = self._prepare_storage()
        return (
            rng,
            data_conc,
            data_error,
            traj,
            array_results,
            array_col_names,
        )

    def _initialize_state(
        self, data_conc: np.ndarray, data_error: np.ndarray
    ) -> _MHState:
        """Choose one valid chain start and evaluate its complete target state.

        Initialization follows an explicit precedence. ``config.initial_params``
        must provide every LPM parameter in model order and lie inside its
        calibration range. Otherwise an enabled prior supplies its MAP; with
        no prior initialization, the LPM's configured defaults are retained.

        The chosen order and values are frozen for proposals, prior evaluation,
        storage, and provenance. The initial modeled concentrations, chi-square,
        and log posterior are evaluated together, and a zero or non-finite target
        density is rejected before the first MH transition.
        """
        if self.config.initial_params is not None:
            expected = list(self.lpm.p.keys())
            provided = list(self.config.initial_params.keys())
            missing = [
                name for name in expected if name not in self.config.initial_params
            ]
            extra = [name for name in provided if name not in self.lpm.p]
            if missing or extra:
                raise ValueError(
                    "initial_params must define exactly the LPM parameters "
                    f"{expected} (missing={missing}, extra={extra})."
                )
            params0 = [float(self.config.initial_params[name]) for name in expected]
            if not all(math.isfinite(value) for value in params0):
                raise ValueError("initial_params values must be finite numbers.")
            if not self.lpm.param_within_calibration_range_array(params0):
                ranges = self.lpm.get_calibration_ranges()
                raise ValueError(
                    f"initial_params are outside the LPM calibration ranges "
                    f"{ranges}: "
                    f"{dict(zip(expected, params0, strict=True))}"
                )
            self.lpm.set_param_from_array(params0)
            self._initialization_source = "config"
        elif self.prior.option:
            self.prior.param_init(self.lpm)
            self._initialization_source = "prior_mode"
        else:
            # The LPM already carries its configured default parameters.
            self._initialization_source = "lpm_default"
        # Freeze the name order used throughout proposals, priors, and storage.
        params = self.lpm.get_parameters_to_array()
        self._initial_params_used = dict(zip(self.lpm.p.keys(), params, strict=True))
        # A chain cannot start outside the exact target support.
        log_p, chi_square, conc = self._log_posterior_eval(
            params, data_conc, data_error
        )
        if not math.isfinite(log_p):
            raise ValueError(
                "Initial parameters have zero or non-finite posterior density: "
                f"{self._initial_params_used}"
            )
        return _MHState(params, log_p, chi_square, conc)

    def perform(self) -> LpmSampleTable:
        """Run and thin the configured Markov chain.

        The loop executes exactly ``config.nstep`` transitions. It stores the
        current state for zero-based iterations satisfying the strict burn-in
        rule ``i > burn_in * nstep`` and ``i % nskip == 0``. The acceptance
        fraction is computed over all transitions and is available through
        :attr:`success_rate`.

        Returns
        -------
        LpmSampleTable
            Retained current states (including rejection repeats), their
            dimensionless ``sqrt(chi_square / n_observations)`` diagnostic, and
            modeled concentrations in each tracer's unit.

        Notes
        -----
        The returned object contains no automatic R-hat, effective sample size,
        or Monte Carlo standard error. Those diagnostics remain required before
        posterior summaries are used scientifically.

        """
        start = perf_counter()

        # Preparation: perform all validation, loading, and allocation once.
        (
            rng,
            data_conc,
            data_error,
            traj,
            array_results,
            array_col_names,
        ) = self._prepare_mcmc()

        # Initialization: select one supported state and evaluate it once.
        state = self._initialize_state(data_conc, data_error)
        n = 0
        nsuccess = 0

        # Transition loop: update the current state, then retain by schedule.
        line = 0
        for i in range(self.config.nstep):
            state, success = self._mcmc_step(
                state,
                data_conc,
                data_error,
                rng,
            )
            if success:
                nsuccess += 1
            if self._should_retain(i):
                # Persist the current state, including repeats after rejection.
                array_results[line] = (
                    state.params
                    + [
                        normalized_residual_norm(
                            state.chi_square,
                            len(state.concentrations),
                        )
                    ]
                    + state.concentrations
                    + [1.0]
                )
                line += 1
                if traj is not None:
                    traj.update(
                        n,
                        state.params,
                        state.log_posterior,
                        accepted=success,
                    )
                    n += 1

        # Consolidate retained joint states without re-evaluating the chain.
        self._success_rate = nsuccess / self.config.nstep
        lpm_results = LpmSampleTable(
            deepcopy(self.lpm), c_names=self.observations.observation_keys()
        )
        lpm_results.replace_frame(pd.DataFrame(array_results, columns=array_col_names))

        # Derive LPM moments row-wise to preserve posterior parameter pairing.
        lpm_results.add_moments()

        # Monitoring is finalized only after the complete chain is available.
        if traj is not None:
            self._finalize_trajectory(traj, n)
            self.trajectory = traj
        else:
            self.trajectory = None

        # A likelihood-free run is an executable check that the chain recovers
        # the configured prior moments; it is not an observational calibration.
        if self.config.likelihood is False and self.prior.option is True:
            self.prior_validation_stats = self.prior.validate_chain_moments(
                traj.path, self.lpm
            )

        self.time_perform = perf_counter() - start

        return lpm_results

    def _parameters_payload(self) -> dict[str, Any]:
        """Build complete sampler metadata for output."""
        data = {}
        data["method"] = self.method
        data["nstep"] = self.config.nstep
        data["burn-in"] = self.config.burn_in
        data["nskip"] = self.config.nskip
        data["retained_sample_count"] = self.config.retained_sample_count()
        data["prior_option"] = self.prior.option
        data["prior_type"] = self.config.prior_type
        data["prior_file"] = self.config.prior_file
        data["likelihood_option"] = self.config.likelihood
        data["monitor"] = self.config.monitor
        data.update(self._resolved_proposal_metadata)
        data["seed"] = self.config.seed
        data["initialization_source"] = self._initialization_source
        data["proposal_kind"] = self.config.proposal_kind
        data["proposal_multiplier"] = self.config.proposal_multiplier
        data["proposal_scales"] = self.config.proposal_scales
        data["proposal_covariance"] = self.config.proposal_covariance
        data.update(self._resolved_prior_metadata)
        for param, value in self._initial_params_used.items():
            data[f"initial_{param}"] = value
        return data

    def write_parameters(self, file_name: str | Path) -> None:
        """Write complete sampler configuration and resolved prior metadata."""
        data = self._parameters_payload()
        write_key_values(file_name, data)

    def write_results_spec(self, data: dict[str, Any]) -> None:
        """Record the transition-level acceptance fraction."""
        data["success_rate"] = self._success_rate

    @property
    def success_rate(self) -> float:
        """Fraction of accepted proposals in the completed chain."""
        return float(self._success_rate)
