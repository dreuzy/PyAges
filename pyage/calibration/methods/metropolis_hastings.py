# -*- coding: utf-8 -*-
"""
Metropolis-Hastings calibration for LPM models.

Purpose
-------
Run MCMC calibration with optional priors, likelihood evaluation, and
trajectory monitoring, then export posterior summaries for analysis.

Author
------
Jean-Raynald de Dreuzy
"""

from __future__ import annotations

import copy as copy
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import pyage.calibration.utils.calibration_core as calbas
import pyage.lpm.core.lpm_dist as LPM_dist
from pyage.calibration.methods.prior import Prior, gauss, make_prior_expo, moments_histo
from pyage.calibration.methods.trajectory import (
    MH_step,
    MH_Trajectory,
    MHConfig,
    TrajOptions,
)
from pyage.calibration.utils.objective_functions import RMSE
from pyage.concentrations.schema import CONCENTRATION_COLUMN, ERROR_COLUMN

__all__ = [
    "MHConfig",
    "MH_Trajectory",
    "MH_step",
    "MetropolisHastings",
    "Prior",
    "TrajOptions",
    "gauss",
    "make_prior_expo",
    "moments_histo",
]


class MetropolisHastings(calbas.CalibrationCore):
    """Calibrate an LPM with a Metropolis-Hastings Markov chain.

    The immutable :class:`MHConfig` controls sampling, prior and monitoring.
    Proposal-step policy is exposed through :attr:`MH_step`; :meth:`perform`
    returns the accepted parameter and concentration distributions.
    """

    def __init__(self, config: MHConfig | None = None, **kwargs):
        """Constructor: definition of  MH parameters"""
        # Parameters
        self.method = "Metropolis_Hastings"
        if config is None:
            raise TypeError(
                "MetropolisHastings now requires config=MHConfig(...). "
                "Pass a MHConfig instance instead of individual parameters."
            )
        if kwargs:
            raise TypeError(
                "MetropolisHastings only accepts config=MHConfig(...). "
                f"Unexpected parameters: {sorted(kwargs.keys())}"
            )
        self.config = config
        # MH step = delta * Delta (parameter bounds)
        self.MH_step = MH_step()
        # A priori distributions
        self.prior = Prior(
            option=self.config.prior_option,
            typ=self.config.prior_type,
            prior_file=self.config.prior_file,
        )
        # Results
        self.__success_rate = 0
        self.__initial_params_used: Dict[str, float] = {}
        self.__initialization_source = ""
        self.prior_validation_stats = None
        self.time_perform = 0

    def update_calibbasis(self, calib_basis: calbas.CalibrationCore) -> None:
        """
        Updates parent class CalibrationCore with calib_basis

        Arguments
        ---------
        calib_basis: CalibrationCore
            Base Class Calibration Problem

        """
        super(MetropolisHastings, self).__dict__.update(calib_basis.__dict__)

    def __param_inc(
        self, p0: List[float], lpm: Any, rng: np.random.Generator
    ) -> List[float]:
        """Increment parameters
        Metropolis_Hastings
        """
        # Required deepcopy to avoid p0 to be modified if not chosen eventually
        p1 = []
        k = 0
        # pf = self.MH_step.delta()
        for key in lpm.p.keys():
            # Perturbation factor of the MCMC MH algorithm, key of the convergence of the algorihm
            p1.append(p0[k] + self.MH_step.value[key] * rng.standard_normal())
            k = k + 1
        return p1

    def __log_posterior_eval(
        self,
        params: List[float],
        data_conc: np.ndarray,
        data_error: np.ndarray,
    ) -> Tuple[float, float, List[float]]:
        """posterior distribution
        It is the logarithm of the posterior probability that is computed to avoid taking the exponential of the difference,
        an hazardous operation for very small or very large numbers
        """
        log_proba = 0
        # If parameters are out of bounds, returns immediatly 0
        if self.lpm.param_within_bounds_array(params) is False:
            return -math.inf, math.inf, []
        if self.config.likelihood:
            [objfunc, conc] = self.objective_function(
                params, data_conc, data_error, conc=True
            )
            log_proba = log_proba - 0.5 * objfunc  # 1
        else:
            objfunc = 0
            conc = [1]
        if self.prior.option:
            log_proba = log_proba + np.log(self.prior.evaluate(self.lpm, params))
        return log_proba, objfunc, conc

    def __prepare_storage(self) -> Tuple[np.ndarray, List[str]]:
        """
        Prepares array for storage of results (optimization of performances)

        Returns
        -------
        sto: np.array
            with the required shape for the storage
        """
        # Number of lines that should be stored
        line = 0
        for i in range(self.config.nstep):
            if (
                i > self.config.burn_in * self.config.nstep
                and i % self.config.nskip == 0
            ):
                line = line + 1
        # Number and name of columns that should be stored
        if self.config.likelihood:
            column = len(self.lpm.p) + 1 + len(self.cdata.names_dates()) + 1
            column_names = (
                self.lpm.get_param_names()
                + ["obj_function"]
                + self.cdata.names_dates()
                + ["param_in_bounds"]
            )
        else:
            column = len(self.lpm.p) + 3
            column_names = (
                self.lpm.get_param_names()
                + ["obj_function"]
                + ["conc"]
                + ["param_in_bounds"]
            )
        # Creation of table
        return np.zeros((line, column), dtype=float), column_names

    def __mcmc_step(
        self,
        params: List[float],
        log_p: float,
        obj_func: float,
        conc: List[float],
        data_conc: np.ndarray,
        data_error: np.ndarray,
        rng: np.random.Generator,
    ) -> Tuple[List[float], float, float, List[float], bool]:
        """
        Purpose
        -------
        Perform one Metropolis-Hastings step.

        Returns
        -------
        tuple
            Updated params, log-posterior, objective function, concentrations,
            and a success flag.
        """
        # Proposal
        params_n = self.__param_inc(params, self.lpm, rng)
        # Evaluate posterior for proposal
        log_pn, obj_func_n, conc_n = self.__log_posterior_eval(
            params_n, data_conc, data_error
        )
        # Accept / reject
        success = False
        if log_pn >= log_p:
            success = True
        else:
            uu = rng.random()
            if np.log(uu) < log_pn - log_p:
                success = True
        if success:
            return params_n, log_pn, obj_func_n, conc_n, True
        return params, log_p, obj_func, conc, False

    def __finalize_trajectory(
        self, traj: "MH_Trajectory", n: int, traj_options: TrajOptions
    ) -> None:
        """
        Purpose
        -------
        Post-process trajectory storage (resize + optional plot/check).
        """
        if not traj_options.monitor:
            return
        traj.resize(n)
        if traj_options.display:
            traj.plot(self.display.directory)
        if traj_options.text:
            traj.check()

    def __prepare_mcmc(
        self,
    ) -> Tuple[
        TrajOptions,
        np.random.Generator,
        np.ndarray,
        np.ndarray,
        Optional["MH_Trajectory"],
        np.ndarray,
        List[str],
    ]:
        """
        Purpose
        -------
        Prepare inputs for the MCMC run.
        """
        # Forces monitoring to true for the test of the algorithm on the sole prior
        traj_monitor = self.config.monitor
        if self.config.likelihood is False and self.prior.option is True:
            traj_monitor = True
        traj_options = TrajOptions(
            monitor=traj_monitor,
            display=self.config.display_traj,
            text=self.config.display_text,
        )
        # Initialization of random number generator
        rng = np.random.default_rng(self.config.seed)
        # Concentration values as array: necessary for optimal numerical efficiency
        data_conc = self.cdata.cv[CONCENTRATION_COLUMN].to_numpy(dtype=float)
        data_error = self.cdata.cv[ERROR_COLUMN].to_numpy(dtype=float)
        # Initialization of stepping interval
        self.MH_step.prepare(self.lpm)
        # Trajectory monitoring
        traj = (
            MH_Trajectory(self.lpm.p.keys(), self.config.nstep)
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
    ) -> Tuple[List[float], float, float, List[float]]:
        """
        Purpose
        -------
        Initialize parameters and compute the initial posterior.
        """
        # Initialization of calibration parameters with default parameters of distribution
        if self.prior.option:
            self.prior.param_init(self.lpm)
            self.__initialization_source = "prior_map"
        elif self.config.initial_params is not None:
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
                    f"{dict(zip(expected, params0))}"
                )
            self.lpm.set_param_from_array(params0)
            self.__initialization_source = "config"
        else:
            # The LPM already carries its configured default parameters.
            self.__initialization_source = "lpm_default"
        # Gets parameters in an array (compulsory for performance of the loop)
        params = self.lpm.get_parameters_to_array()
        self.__initial_params_used = dict(zip(self.lpm.p.keys(), params))
        # Value of the posterior distribution for initial set of parameters
        log_p, obj_func, conc = self.__log_posterior_eval(params, data_conc, data_error)
        return params, log_p, obj_func, conc

    def perform(self) -> LPM_dist.LpmDist:
        """Run the configured Markov chain.

        Returns
        -------
        LpmDist
            Accepted parameters, objective values, and concentration solutions.
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
        params, log_p, obj_func, conc = self.__initialize_state(data_conc, data_error)
        n = 0
        nsuccess = 0

        # --------------- MONTE CARLO MARKOV CHAIN LOOP ------------
        line = 0
        for i in range(self.config.nstep):
            params, log_p, obj_func, conc, success = self.__mcmc_step(
                params,
                log_p,
                obj_func,
                conc,
                data_conc,
                data_error,
                rng,
            )
            if success:
                # print(nsuccess, params[0],params[1],log_p)
                nsuccess += 1
            if (
                i > self.config.burn_in * self.config.nstep
                and i % self.config.nskip == 0
            ):
                # Storage : everything relative to params and not params !!! (sources of errors to take params_n)
                array_results[line] = (
                    params + [RMSE(obj_func, len(conc))] + conc + [1.0]
                )
                line += 1
                if traj_options.monitor:
                    traj.update(n, params, -log_p)
                    traj.inc_one(n)
                    n += 1

        # --------------- POSTPROCESSING PHASE -------------------
        # Results consolidation
        self.__success_rate = nsuccess / self.config.nstep
        lpm_results = LPM_dist.LpmDist(self.lpm, c_names=self.cdata.names_dates())
        lpm_results.fill_np_array(array_results, array_col_names)

        # Adds statistical characteritics to the stored distributions
        lpm_results = lpm_results.stats_distribution()

        # Displays Trajectory
        if traj_options.monitor:
            self.__finalize_trajectory(traj, n, traj_options)

        # Checks algorithm with prior distribution and no likelihood
        if self.config.likelihood is False and self.prior.option is True:
            self.prior_validation_stats = self.prior.validation_MH_prior(
                traj.path, self.lpm
            )

        end = time.time()
        self.time_perform = end - start

        return lpm_results

    def __posterior_dir(self, file: str | Path) -> Path:
        """
        Purpose
        -------
        Resolve the shared posterior directory from a results file path.
        """
        file_path = Path(file).resolve()
        try:
            folder_root = file_path.parents[3]
        except IndexError as exc:
            raise ValueError(
                f"Cannot derive posterior directory from {file_path} "
                "(expected at least 4 parent levels)."
            ) from exc
        posterior_dir = folder_root / "posterior_distributions"
        posterior_dir.mkdir(parents=True, exist_ok=True)
        return posterior_dir

    def __set_display_directory(self, directory: Path) -> Path:
        """
        Purpose
        -------
        Update display output directory.
        """
        self.display_options.directory = directory
        return directory

    def write_posterior(self, lpm_results: LPM_dist.LpmDist, file: str | Path) -> Path:
        """
        Saves posterior to a specific folder.

        Parameters
        ----------
        lpm_results : LPM_dist
            Distributions of calibrated LPMs.
        file : str or Path
            Current root file where all results are commonly stored.
            Posterior will be stored in another folder common to all posteriors.
        """
        posterior_dir = self.__posterior_dir(file)
        self.__set_display_directory(posterior_dir)

        # store posterior distributions here if needed.

        return posterior_dir

    def __write_kv_file(self, file_name: str | Path, data: Dict[str, Any]) -> None:
        """
        Purpose
        -------
        Write key/value pairs to a tab-separated file.
        """
        with open(file_name, "w") as handle:
            for key, val in data.items():
                handle.write(f"{key}\t{val}\n")

    def __parameters_payload(self) -> Dict[str, Any]:
        """
        Purpose
        -------
        Build the parameter payload for output.
        """
        data = {}
        data["method"] = self.method
        data["nstep"] = self.config.nstep
        data["burn-in"] = self.config.burn_in
        data["prior_option"] = self.prior.option
        data["likelihood_option"] = self.config.likelihood
        self.MH_step.save_param(data)
        data["seed"] = self.config.seed
        data["initialization_source"] = self.__initialization_source
        for param, value in self.__initial_params_used.items():
            data[f"initial_{param}"] = value
        return data

    def write_parameters(self, file_name: str | Path) -> None:
        """
        Writes parameters of calibration
        """
        data = self.__parameters_payload()
        self.__write_kv_file(file_name, data)

    def write_results_spec(self, data: Dict[str, Any]) -> None:
        """
        Specific contribution of the daughter class to the calibration results

        Argumments
        ----------
        data: dictionary
            results to be stored

        """
        data["success_rate"] = self.__success_rate
