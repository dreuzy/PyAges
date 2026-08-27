# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Metropolis-Hastings calibration for lumped-parameter models."""

from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pyages.calibration.methods.base import CalibrationMethod
from pyages.calibration.methods.prior import Prior
from pyages.calibration.methods.trajectory import (
    MHConfig,
    MHStep,
    MHTrajectory,
    TrajOptions,
)
from pyages.calibration.mh_proposals import GaussianRandomWalk
from pyages.calibration.outputs import write_key_values
from pyages.calibration.utils.objective_functions import normalized_residual_norm
from pyages.concentrations.schema import CONCENTRATION_COLUMN, ERROR_COLUMN
from pyages.lpm.samples.table import LpmSampleTable

__all__ = [
    "MHConfig",
    "MHStep",
    "MHTrajectory",
    "MetropolisHastings",
    "TrajOptions",
]


class MetropolisHastings(CalibrationMethod):
    r"""Sample an LPM posterior with a Metropolis-Hastings chain.

    For parameters :math:`\theta` within the configured LPM bounds, the target
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
    Out-of-bounds proposals and zero-support prior values have log target
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

    def __init__(self, config: MHConfig | None = None):
        """Initialize the sampler from one immutable scientific configuration."""
        super().__init__()
        # Parameters
        self.method = "Metropolis_Hastings"
        if config is None:
            raise TypeError(
                "MetropolisHastings now requires config=MHConfig(...). "
                "Pass a MHConfig instance instead of individual parameters."
            )
        self.config = config
        self.proposal_step = MHStep(
            config.componentwise_source,
            config.componentwise_fraction,
        )
        # A priori distributions
        self.prior = Prior(
            option=self.config.prior_option,
            typ=self.config.prior_type,
            prior_file=self.config.prior_file,
        )
        # Results
        self.__success_rate = 0
        self.__initial_params_used: dict[str, float] = {}
        self.__initialization_source = ""
        self.prior_validation_stats = None
        self.trajectory: MHTrajectory | None = None
        self.time_perform = 0
        self._proposal: GaussianRandomWalk | None = None

    def __draw_proposal(
        self, p0: list[float], lpm: Any, rng: np.random.Generator
    ) -> list[float]:
        """Draw one unbounded proposal from the configured random walk."""
        if self._proposal is not None:
            return self._proposal.draw(p0, rng).tolist()
        # Scalar draws are intentional: they make the default seeded protocol
        # independent of NumPy's multivariate-normal implementation details.
        return [
            p0[k] + self.proposal_step.value[key] * rng.standard_normal()
            for k, key in enumerate(lpm.p.keys())
        ]

    def __prepare_proposal(self) -> None:
        """Resolve an optional fixed Gaussian proposal after model setup."""
        kind = self.config.proposal_kind
        if kind == "componentwise":
            if (
                any(
                    value is not None
                    for value in (
                        self.config.proposal_scales,
                        self.config.proposal_covariance,
                    )
                )
                or self.config.proposal_multiplier != 1.0
            ):
                raise ValueError(
                    "componentwise does not accept explicit proposal parameters"
                )
            self._proposal = None
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

    def __log_posterior_eval(
        self,
        params: list[float],
        data_conc: np.ndarray,
        data_error: np.ndarray,
    ) -> tuple[float, float, list[float]]:
        r"""Evaluate ``-chi_square/2 + log(prior)`` in log space.

        The normalization constants of the independent Gaussian likelihood do
        not depend on LPM parameters and are omitted. Log space prevents
        underflow. Parameter bounds and prior supports preserve exact zero
        density outside their configured domains.
        """
        log_proba = 0
        # Bounds are part of the target support, not a numerical penalty.
        if self.lpm.param_within_bounds_array(params) is False:
            return -math.inf, math.inf, []
        if self.config.likelihood:
            [chi_square, conc] = self.objective_function(
                params, data_conc, data_error, conc=True
            )
            log_proba = log_proba - 0.5 * chi_square
        else:
            chi_square = 0
            # Concentrations are not evaluated without a likelihood, but the
            # result table keeps the same canonical observation schema.
            conc = [math.nan] * len(data_conc)
        if self.prior.option:
            log_proba = log_proba + self.prior.log_evaluate(self.lpm, params)
        return log_proba, chi_square, conc

    def __should_retain(self, iteration: int) -> bool:
        """Return whether one zero-based MCMC iteration must be stored."""
        return (
            iteration > self.config.burn_in * self.config.nstep
            and iteration % self.config.nskip == 0
        )

    def __prepare_storage(self) -> tuple[np.ndarray, list[str]]:
        """
        Prepares array for storage of results (optimization of performances)

        Returns
        -------
        sto: np.array
            with the required shape for the storage
        """
        # Number of lines that should be stored
        row_count = sum(
            self.__should_retain(iteration) for iteration in range(self.config.nstep)
        )
        # Likelihood-free runs leave concentration values missing while using
        # the same canonical columns as likelihood-based calibrations.
        concentration_names = self.observations.observation_keys()
        column_names = (
            self.lpm.get_param_names()
            + ["obj_function"]
            + concentration_names
            + ["param_in_bounds"]
        )
        column = len(column_names)
        # Creation of table
        return np.zeros((row_count, column), dtype=float), column_names

    def __mcmc_step(
        self,
        params: list[float],
        log_p: float,
        chi_square: float,
        conc: list[float],
        data_conc: np.ndarray,
        data_error: np.ndarray,
        rng: np.random.Generator,
    ) -> tuple[list[float], float, float, list[float], bool]:
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
        # Proposal
        params_n = self.__draw_proposal(params, self.lpm, rng)
        # Evaluate posterior for proposal
        log_pn, chi_square_n, conc_n = self.__log_posterior_eval(
            params_n, data_conc, data_error
        )
        # Accept / reject
        success = False
        log_hastings = (
            0.0
            if self._proposal is None
            else self._proposal.log_hastings_ratio(params, params_n)
        )
        if log_pn + log_hastings >= log_p:
            success = True
        else:
            uu = rng.random()
            if np.log(uu) < log_pn - log_p + log_hastings:
                success = True
        if success:
            return params_n, log_pn, chi_square_n, conc_n, True
        return params, log_p, chi_square, conc, False

    def __finalize_trajectory(
        self, traj: "MHTrajectory", n: int, traj_options: TrajOptions
    ) -> None:
        """Resize and optionally display the retained trajectory."""
        if not traj_options.monitor:
            return
        traj.resize(n)
        if traj_options.display:
            traj.plot(self.display_options.directory)
        if traj_options.text:
            traj.check()

    def __prepare_mcmc(
        self,
    ) -> tuple[
        TrajOptions,
        np.random.Generator,
        np.ndarray,
        np.ndarray,
        MHTrajectory | None,
        np.ndarray,
        list[str],
    ]:
        """Prepare observations, prior, proposal, RNG, and result storage."""
        # Prior-only validation requires retained trajectory values.
        traj_monitor = self.config.monitor
        if self.config.likelihood is False and self.prior.option is True:
            traj_monitor = True
        traj_options = TrajOptions(
            monitor=traj_monitor,
            display=self.config.display_traj,
            text=self.config.display_text,
        )
        rng = np.random.default_rng(self.config.seed)
        data_conc = self.observations.frame[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        data_error = self.observations.frame[ERROR_COLUMN].to_numpy(dtype=float)
        if self.config.proposal_kind == "componentwise":
            self.proposal_step.prepare(self.lpm)
        self.__prepare_proposal()
        # Trajectory monitoring
        traj = (
            MHTrajectory(self.lpm.p.keys(), self.config.nstep)
            if traj_options.monitor
            else None
        )
        # Loads a priori for the distribution of parameters
        self.prior.load(self.lpm)
        # Initialization of results structure
        array_results, array_col_names = self.__prepare_storage()
        return (
            traj_options,
            rng,
            data_conc,
            data_error,
            traj,
            array_results,
            array_col_names,
        )

    def __initialize_state(
        self, data_conc: np.ndarray, data_error: np.ndarray
    ) -> tuple[list[float], float, float, list[float]]:
        """Initialize parameters and evaluate the initial log-posterior."""
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
            if not self.lpm.param_within_bounds_array(params0):
                bounds = {
                    name: [self.lpm.get_p_min(name), self.lpm.get_p_max(name)]
                    for name in expected
                }
                raise ValueError(
                    f"initial_params are outside the LPM bounds {bounds}: "
                    f"{dict(zip(expected, params0, strict=True))}"
                )
            self.lpm.set_param_from_array(params0)
            self.__initialization_source = "config"
        elif self.prior.option:
            self.prior.param_init(self.lpm)
            self.__initialization_source = "prior_map"
        else:
            # The LPM already carries its configured default parameters.
            self.__initialization_source = "lpm_default"
        # Gets parameters in an array (compulsory for performance of the loop)
        params = self.lpm.get_parameters_to_array()
        self.__initial_params_used = dict(zip(self.lpm.p.keys(), params, strict=True))
        # Value of the posterior distribution for initial set of parameters
        log_p, chi_square, conc = self.__log_posterior_eval(
            params, data_conc, data_error
        )
        if not math.isfinite(log_p):
            raise ValueError(
                "Initial parameters have zero or non-finite posterior density: "
                f"{self.__initial_params_used}"
            )
        return params, log_p, chi_square, conc

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

        start = time.time()

        # --------------- PREPARATION PHASE ------------------------
        (
            traj_options,
            rng,
            data_conc,
            data_error,
            traj,
            array_results,
            array_col_names,
        ) = self.__prepare_mcmc()

        # --------------- INITIALIZATION PHASE ----------------------
        params, log_p, chi_square, conc = self.__initialize_state(data_conc, data_error)
        n = 0
        nsuccess = 0

        # --------------- MONTE CARLO MARKOV CHAIN LOOP ------------
        line = 0
        for i in range(self.config.nstep):
            params, log_p, chi_square, conc, success = self.__mcmc_step(
                params,
                log_p,
                chi_square,
                conc,
                data_conc,
                data_error,
                rng,
            )
            if success:
                nsuccess += 1
            if self.__should_retain(i):
                # Persist the current state, including repeats after rejection.
                array_results[line] = (
                    params
                    + [normalized_residual_norm(chi_square, len(conc))]
                    + conc
                    + [1.0]
                )
                line += 1
                if traj_options.monitor:
                    traj.update(n, params, log_p, accepted=success)
                    n += 1

        # --------------- POSTPROCESSING PHASE -------------------
        # Results consolidation
        self.__success_rate = nsuccess / self.config.nstep
        lpm_results = LpmSampleTable(
            self.lpm, c_names=self.observations.observation_keys()
        )
        lpm_results.replace_frame(pd.DataFrame(array_results, columns=array_col_names))

        # Derive LPM moments for every retained joint sample.
        lpm_results.add_moments()

        # Displays Trajectory
        if traj_options.monitor:
            self.__finalize_trajectory(traj, n, traj_options)
            self.trajectory = traj
        else:
            self.trajectory = None

        # Checks algorithm with prior distribution and no likelihood
        if self.config.likelihood is False and self.prior.option is True:
            self.prior_validation_stats = self.prior.validation_MH_prior(
                traj.path, self.lpm
            )

        end = time.time()
        self.time_perform = end - start

        return lpm_results

    def __parameters_payload(self) -> dict[str, Any]:
        """Build complete sampler metadata for output."""
        data = {}
        data["method"] = self.method
        data["nstep"] = self.config.nstep
        data["burn-in"] = self.config.burn_in
        data["nskip"] = self.config.nskip
        data["prior_option"] = self.prior.option
        data["prior_type"] = self.config.prior_type
        data["prior_file"] = self.config.prior_file
        data["likelihood_option"] = self.config.likelihood
        data["monitor"] = self.config.monitor
        if self.config.proposal_kind == "componentwise":
            self.proposal_step.add_metadata(data)
        data["seed"] = self.config.seed
        data["initialization_source"] = self.__initialization_source
        data["proposal_kind"] = self.config.proposal_kind
        data["proposal_multiplier"] = self.config.proposal_multiplier
        data["proposal_scales"] = self.config.proposal_scales
        data["proposal_covariance"] = self.config.proposal_covariance
        for param, distribution in self.prior.MHapriori_dist.items():
            data[f"prior_distribution_{param}"] = distribution
            if self.config.prior_type == "parametric":
                data[f"prior_parameters_{param}"] = self.prior.MHapriori_para[param]
            elif self.config.prior_file:
                source = Path(f"{self.config.prior_file}_{param}.txt")
                if source.is_file():
                    data[f"prior_sha256_{param}"] = hashlib.sha256(
                        source.read_bytes()
                    ).hexdigest()
                    data[f"prior_grid_points_{param}"] = len(
                        self.prior.MHapriori_para[param]
                    )
        for param, value in self.__initial_params_used.items():
            data[f"initial_{param}"] = value
        return data

    def write_parameters(self, file_name: str | Path) -> None:
        """Write complete sampler configuration and resolved prior metadata."""
        data = self.__parameters_payload()
        write_key_values(file_name, data)

    def write_results_spec(self, data: dict[str, Any]) -> None:
        """Record the transition-level acceptance fraction."""
        data["success_rate"] = self.__success_rate

    @property
    def success_rate(self) -> float:
        """Fraction of accepted proposals in the completed chain."""
        return float(self.__success_rate)
