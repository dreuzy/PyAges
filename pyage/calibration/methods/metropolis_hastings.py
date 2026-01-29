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

import copy as copy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from pathlib import Path
import sys
import time
from scipy.interpolate import interp1d

from pyage.calibration.utils.objective_functions import RMSE
import pyage.calibration.utils.calibration_core as calbas
import pyage.LPM.core.lpm_dist as LPM_dist
import pyage.global_parameters as gp                              


def make_prior_expo(
    x_data: Sequence[float],
    y_data: Sequence[float],
    xmin: float = 0.0,
    xmax: float = 70.0,
    n_points: int = 2000,
    decay_left: float = 10.0,
    decay_right: float = 10.0,
    normalize: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Purpose
    -------
    Build a continuous PDF from discrete histogram points with linear
    interpolation and exponential tails.
    
    Parameters
    ----------
    x_data : array-like
        Histogram bin centers.
    y_data : array-like
        Histogram values.
    xmin : float, optional
        Minimum grid bound.
    xmax : float, optional
        Maximum grid bound.
    n_points : int, optional
        Number of grid samples.
    decay_left : float, optional
        Left-side exponential decay rate.
    decay_right : float, optional
        Right-side exponential decay rate.
    normalize : bool, optional
        Normalize area to 1 if True.
    
    Returns
    -------
    x_cont : ndarray
        Regular grid between bounds.
    y_cont : ndarray
        Continuous PDF values on the grid.
    """
    x_data = np.asarray(x_data)
    y_data = np.asarray(y_data)

    # interpolation linéaire
    interp_fun = interp1d(x_data, y_data, kind="linear",
                          bounds_error=False, fill_value=0)

    # grille continue
    x_cont = np.linspace(xmin, xmax, n_points)
    y_interp = interp_fun(x_cont)

    # prolongement exponentiel
    y_cont = y_interp.copy()
    left_mask = x_cont < x_data.min()
    right_mask = x_cont > x_data.max()

    if y_data[0] > 0:
        y_cont[left_mask] = y_data[0] * np.exp(-decay_left * (x_data[0] - x_cont[left_mask]))
    if y_data[-1] > 0:
        y_cont[right_mask] = y_data[-1] * np.exp(-decay_right * (x_cont[right_mask] - x_data[-1]))

    # normalisation
    if normalize:
        area = np.trapezoid(y_cont, x_cont)
        if area > 0:
            y_cont /= area

    return x_cont, y_cont


def gauss(x: float, x0: float, sigma: float) -> float:
    """
    Purpose
    -------
    Evaluate the Gaussian PDF at a single point.
    """
    num = math.exp( - ( x - x0 )**2 / ( 2.0 * sigma **2 ) )
    den = math.sqrt( 2 * math.pi * sigma **2)
    return  num / den


def moments_histo(hist: np.ndarray) -> Tuple[float, float]:
    n=len(hist[:,0])
    sum0=sum1=sum2=0
    for i in range(n): 
        sum0=sum0+hist[i,1]
        sum1=sum1+hist[i,0]*hist[i,1]
        sum2=sum2+hist[i,0]**2*hist[i,1]
    sum1=sum1/sum0
    sum2=sum2/sum0-sum1**2
    return sum1,sum2


@dataclass(frozen=True)
class MHConfig:
    """
    Purpose
    -------
    Compute mean and variance from a histogram array.
    """

    nstep: int = 10000
    burn_in: float = 0.2
    nskip: int = 10
    prior_option: bool = True
    prior_type: str = "parametric"
    likelihood: bool = True
    monitor: bool = True
    display_traj: bool = False
    display_text: bool = False
    prior_file: str = ""
    lpm_number: int = 10
    seed: int = 12345


@dataclass(frozen=True)
class TrajOptions:
    """Configuration for trajectory monitoring and display."""

    monitor: bool
    display: bool
    text: bool


class MH_Trajectory: 
    """ 
        Trajectory of optimization function
            Used for monitoring
            Adds significant numerical load, Should not be run systematically
        
        Attributes
        ----------
        path: dataframe
            Storage of Trajectory 
            Example
        
        Methods
        -------
        
        
    """


    def __init__(self, params: Iterable[str], nstep: int) -> None:
        """
        """
        names = []
        for t in params:
            names.append(t)
        names.append('-log_posterior')
        self.n_inc = len(names)
        names.append('incrementation')
        self.path = pd.DataFrame(data=None, index=range(nstep), columns=names, dtype=None, copy=False)


    def update(self, i: int, params: List[float], log_posterior: float) -> None:
        """ Updates strucutre at step i 
        """
        temp = copy.deepcopy(params)
        temp.append(-log_posterior)
        temp.append(0)
        self.path.iloc[i,:]=temp


    def inc_one(self, i: int) -> None:
        self.path.iloc[i,self.n_inc] = 1


    def check(self) -> None:
        """ A posteriori distribution should give values of cocnentration in the expected range
            With expected variance
        """
        columns = list(self.path)
        for t in columns:
            temp = self.path.iloc[:][t]
            temp_mean = np.nanmean(self.path.iloc[:][t].to_numpy(),dtype='float')
            temp_var = np.nanvar(self.path.iloc[:][t].to_numpy(),dtype='float')
            print('%.4f' % temp_mean, '%.4f' % np.sqrt(temp_var), '<> & \u03C3 of', t)


    def resize(self, n: int) -> None:
        """
        """
        self.path.drop(self.path.tail(self.path.shape[0]-n).index, inplace = True)


    def plot(self, directory_name: Optional[str]) -> None:
        """ Graphical Representation of Trajectory
        """
        columns = list(self.path)
        for t in columns:
            if(t=='-log_posterior' or t=='objective_function'):
                ax = self.path.plot.line(y=t,logy=False)
            else: 
                ax = self.path.plot.line(y=t,logy=False)
            fig = ax.get_figure()
            if directory_name != None : 
                fig.savefig(os.path.join(directory_name,'MH_trajectory_'+t))
                plt.close(fig)


class MH_step: 
    """ Computation Method of Metropolis Hastings Step"""


    def __init__(self) -> None:
        self.method = "prop"     # selection by proportionality of the boundary interval "prop" OR by value "value"
        self.value = 1
        self.prop = 0.1
        self.interval = 0 


    def define_by_value(self) -> None: 
        self.method = "value"


    def define_by_prop(self, prop: float) -> None:
        self.method = "prop"
        self.prop = prop


    def define_value_by_interval(self, lpm: Any) -> None:
        self.interval={}
        self.value={}
        for key in lpm.p.keys():
            # Perturbation factor of the MCMC MH algorithm, key of the convergence of the algorihm
            self.interval[key] = lpm.get_param_range(key)
            self.value[key] = self.prop * self.interval[key]


    def load_MHsteps(self, lpm: Any) -> None:
        from data_io import lpm_params

        data_dir = Path(lpm.lpm_parameter_file("params.yaml")).parent.parent
        params = lpm_params.load_params(lpm.name, data_dir)
        values = lpm_params.get_steps(params)
        if not values:
            raise ValueError(
                f"No MH step values found in params.yaml for {lpm.name}."
            )
        self.value = values


    def prepare(self, lpm: Any) -> None:
        """ Driving prepration function """
        if self.method == "prop" : 
            self.define_value_by_interval(lpm)
        else:
            self.load_MHsteps(lpm)


    def save_param(self, data: Dict[str, Any]) -> None:
        """ writes delta step parameters in data for parameter outputs """
        data['MH_delta_method'] = self.method
        for param in self.value : 
            data['MH_delta_'+param] = self.value[param]


class Prior() :
    """ 
    prior distribution of the Bayesian identification method 
    prior can be 
        - a parametric distribution 
        - an empirical distribution 
        
    Attributes, private
    -------------------
        __option: bool
            False : no prior
            True : prior
        __typ: string
            "parametric": parametric distribution 
            "empirical": empirical distribution (defined by an histogram)
    """


    def __init__(self, option: bool = True, typ: str = "parametric", prior_file: str = "") -> None:
        """
        Purpose
        -------
        Initialize the prior configuration.

        Parameters
        ----------
        option : bool
            Enable or disable the prior.
        typ : str
            Prior type ("parametric" or "empirical").
        prior_file : str
            Path prefix for empirical prior files.
        """
        # Parameters
        self.option = option
        self.typ = typ
        self.prior_file = prior_file
        self.MHapriori_dist = {}
        self.MHapriori_para = {}


    def __param_init_parametric(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """
        Purpose
        -------
        Pick an initial parameter value from a parametric prior.
        """
        dist = self.MHapriori_dist[key]
        mu_or_a = self.MHapriori_para[key][0]
        sig_or_b = self.MHapriori_para[key][1]

        if dist == "normal":
            if strategy == "map":
                x = mu_or_a
            else:
                x = (
                    rng.normal(mu_or_a, sig_or_b)
                    if hasattr(rng, "normal") else np.random.normal(mu_or_a, sig_or_b)
                )
            x = float(np.clip(x, pmin, pmax))
            return x

        if dist == "uniform":
            a, b = mu_or_a, sig_or_b
            if strategy == "map":
                x = 0.5 * (a + b)
            else:
                x = rng.uniform(a, b) if hasattr(rng, "uniform") else a + (b - a) * rng.random()
            x = float(np.clip(x, pmin, pmax))
            return x

        return 0.5 * (pmin + pmax)


    def __param_init_empirical(
        self,
        key: str,
        pmin: float,
        pmax: float,
        rng: np.random.Generator,
        strategy: str,
    ) -> float:
        """
        Purpose
        -------
        Pick an initial parameter value from an empirical prior.
        """
        arr = self.MHapriori_para[key]
        xs, ps = arr[:, 0], arr[:, 1]
        if np.all((ps <= 0) | ~np.isfinite(ps)):
            return 0.5 * (pmin + pmax)
        if strategy == "map":
            x = float(xs[np.argmax(ps)])
        else:
            cdf = np.cumsum(0.5 * (ps[:-1] + ps[1:]) * (xs[1:] - xs[:-1]))
            cdf = np.concatenate([[0.0], cdf])
            if cdf[-1] > 0:
                cdf /= cdf[-1]
                u = rng.random() if hasattr(rng, "random") else np.random.random()
                x = float(np.interp(u, cdf, xs))
            else:
                x = float(xs[np.argmax(ps)])
        return float(np.clip(x, pmin, pmax))


    def param_init(self, lpm: Any, strategy: str = "map") -> None:
        """
        Purpose
        -------
        Initialize LPM parameters from the prior distribution.

        Parameters
        ----------
        lpm : Any
            LPM instance to initialize.
        strategy : str
            Initialization strategy ("map" or "sample").
        """
        rng = np.random.default_rng()
    
        params0 = []
    
        for key in lpm.p.keys():
            pmin = lpm.get_p_min(key)
            pmax = lpm.get_p_max(key)
    
            if self.typ == "parametric":
                x = self.__param_init_parametric(key, pmin, pmax, rng, strategy)
            elif self.typ == "empirical":
                x = self.__param_init_empirical(key, pmin, pmax, rng, strategy)
            else:
                x = 0.5 * (pmin + pmax)

            params0.append(x)        
        
        lpm.set_param_from_array(params0)


    def __load_parametric_priors(self, lpm: Any) -> None:
        """
        Purpose
        -------
        Load parametric priors from params.yaml.
        """
        from data_io import lpm_params

        data_dir = Path(lpm.lpm_parameter_file("params.yaml")).parent.parent
        params = lpm_params.load_params(lpm.name, data_dir)
        priors = lpm_params.get_priors(params)
        for name, prior in priors.items():
            ptype = prior.get("type")
            if not ptype:
                continue
            self.MHapriori_dist[name] = ptype
            self.MHapriori_para[name] = []
            if ptype == "uniform":
                self.MHapriori_para[name].append(prior.get("min"))
                self.MHapriori_para[name].append(prior.get("max"))
            elif ptype in {"normal", "gaussian"}:
                self.MHapriori_para[name].append(prior.get("mean"))
                self.MHapriori_para[name].append(prior.get("std"))
            else:
                args = prior.get("args", [])
                if len(args) >= 2:
                    self.MHapriori_para[name].append(args[0])
                    self.MHapriori_para[name].append(args[1])
        if not self.MHapriori_dist:
            raise ValueError(
                f"No MH priors found in params.yaml for {lpm.name}."
            )


    def __load_empirical_priors(self, lpm: Any) -> None:
        """
        Purpose
        -------
        Load empirical priors from histogram files.
        """
        self.MHapriori_para = {}
        for param in lpm.get_param_names():
            self.MHapriori_para[param] = pd.DataFrame.to_numpy(
                pd.read_csv(self.prior_file + "_" + param + ".txt", sep="\t")
            )
            histo_x = self.MHapriori_para[param][:, 0]
            histo_y = self.MHapriori_para[param][:, 1]

            decay = 500.0 / abs(lpm.get_p_min(param) - lpm.get_p_max(param))
            pdf_x, pdf_p = make_prior_expo(
                histo_x,
                histo_y,
                xmin=lpm.get_p_min(param),
                xmax=lpm.get_p_max(param),
                n_points=101,
                decay_left=decay,
                decay_right=decay,
            )

            self.MHapriori_para[param] = np.column_stack((pdf_x, pdf_p))


    def load(self, lpm: Any) -> None:
        """
        Purpose
        -------
        Load the prior definitions into memory.
        """
        if self.option:
            if self.typ == "parametric":
                self.__load_parametric_priors(lpm)
                return
            elif self.typ == "empirical":
                self.__load_empirical_priors(lpm)
            else:
                raise ValueError(f"Unsupported prior type: {self.typ}")


    def __evaluate_parametric(self, lpm: Any, params: List[float]) -> float:
        """
        Purpose
        -------
        Evaluate the parametric prior density.
        """
        proba = 1.0
        ikey = 0
        for key in lpm.p.keys():
            if self.MHapriori_dist[key] == "normal":
                proba *= gauss(
                    params[ikey],
                    self.MHapriori_para[key][0],
                    self.MHapriori_para[key][1],
                )
            elif self.MHapriori_dist[key] == "uniform":
                if (
                    params[ikey] > self.MHapriori_para[key][0]
                    and params[ikey] < self.MHapriori_para[key][1]
                ):
                    proba = proba / np.abs(
                        self.MHapriori_para[key][1] - self.MHapriori_para[key][0]
                    )
                else:
                    proba = 0
            elif self.MHapriori_dist[key] == "lognormal":
                raise ValueError("Lognormal prior is not implemented for errors.")
            else:
                raise ValueError(
                    f"Unsupported prior distribution: {self.MHapriori_dist[key]}"
                )
            ikey = ikey + 1
        return proba


    def __evaluate_empirical(self, lpm: Any, params: List[float]) -> float:
        """
        Purpose
        -------
        Evaluate the empirical prior density.
        """
        proba = 1.0
        ikey = 0
        for key, param in zip(lpm.p.keys(), lpm.get_param_names()):
            if params[ikey] < self.MHapriori_para[param][:, 0][0]:
                proba = 0
            elif params[ikey] > self.MHapriori_para[param][:, 0][-1]:
                proba = 0
            else:
                proba *= self.MHapriori_para[param][
                    np.argsort(abs(self.MHapriori_para[param][:, 0] - params[ikey]))[0]
                ][1]
            ikey = ikey + 1
        return proba


    def evaluate(self, lpm: Any, params: List[float]) -> float:
        """
        Purpose
        -------
        Evaluate the prior density for the current parameters.
        """
        if self.typ == "parametric":
            proba = self.__evaluate_parametric(lpm, params)
        elif self.typ == "empirical":
            proba = self.__evaluate_empirical(lpm, params)
        else:
            raise ValueError(f"Unsupported prior type: {self.typ}")
        # To avoid any issue by taking the next log of the probability 
        if proba <= 1e-300:
            proba = 1e-300
        return proba


    def validation_MH_prior(self, path: pd.DataFrame, lpm: Any) -> Dict[str, Dict[str, float]]:
        """
        Purpose
        -------
        Compare sampled prior moments with theoretical expectations.
        """
        # Mean and Variance of sampled distribution
        apriori_sampled={}
        for key in lpm.p.keys():
            apriori_sampled[key]=[np.nanmean(path.iloc[:][key].to_numpy(),dtype='float'),                                    np.nanvar(path.iloc[:][key].to_numpy(),dtype='float')]
        
        # Mean and Variance of theory
        apriori_theory=copy.deepcopy(apriori_sampled)
        if self.typ == "parametric": 
            for key in lpm.p.keys():
                # print('%.4f' % temp_mean, '%.4f' % np.sqrt(temp_var), '<> & sigma of', key, 'computed')
                # print('%.4f' % MHapriori_para[key][0], '%.4f' % MHapriori_para[key][1], '<> & sigma of', key, 'target')
                if self.MHapriori_dist[key] == 'normal':
                    apriori_theory[key]=[self.MHapriori_para[key][0],                                         self.MHapriori_para[key][1]**2]
                elif self.MHapriori_dist[key] == 'uniform':
                    apriori_theory[key]=[(self.MHapriori_para[key][0] + self.MHapriori_para[key][1]) / 2,                                          ((self.MHapriori_para[key][1] - self.MHapriori_para[key][0]) / np.sqrt(12))**2]
                
        elif self.typ == "empirical": 
            for key in lpm.p.keys():
                apriori_theory[key] = moments_histo(self.MHapriori_para[key])
                
        MH_difference=copy.deepcopy(apriori_sampled)
        for key in lpm.p.keys():
            MH_difference[key][0] = 100 * (1-apriori_sampled[key][0]/apriori_theory[key][0])
            MH_difference[key][1] = 100 * (1-apriori_sampled[key][1]/apriori_theory[key][1])

        return {
            "sampled": {k: {"mean": v[0], "var": v[1]} for k, v in apriori_sampled.items()},
            "theory": {k: {"mean": v[0], "var": v[1]} for k, v in apriori_theory.items()},
            "difference_percent": {k: {"mean": v[0], "var": v[1]} for k, v in MH_difference.items()},
        }
class MetropolisHastings(calbas.CalibrationCore) : 
    """ 
    Metropolis_Hastinvs Monte-Carlo Markov Chain Algorithm (MH MCMC)
        to calibrate lpm accounting for uncertainty in the data and possibly for a-priori distributions on parameters 
        Requires large number of evaluations of the objective function (10^5-10^6-10^7)
        
    Reference in groundwater dating litterature: 
        Massoudieh, A., S. Sharifi, and D. K. Solomon (2012), 
            Bayesian evaluation of groundwater age distribution using radioactive tracers 
            and anthropogenic chemicals, Water Resources Research, 48, doi:10.1029/2012wr011815.
            posterior distribution: equation (16)
    Reference for the importance of jumping rules and stepsize
    In a nutshell, stepsize of MH is large enough to ensure a good space coverage at the cost of computational under-optimality
            Optimatlly, stepsize is of the order of 2.5 times the variance of the posterior distribution (Liu, 2021)
            Automatic adaptation of the stepsize may bias the algorithm with no guarantee of convergence (Beskos, 2013)
            Optimality is reached when acceptance rate is around 0.234 (Atchade, 2011)
        Beskos, A., N. Pillai, G. Roberts, J. M. Sanz-Serna, and A. Stuart (2013), 
            Optimal tuning of the hybrid Monte Carlo algorithm, Bernoulli, 19(5A), 1501-1534, doi:10.3150/12-bej414.
        Liu, J. S., and C. Dai Metropolis Jumping Rules, in Wiley StatsRef: 
            Statistics Reference Online, edited, pp. 1-12, doi:https://doi.org/10.1002/9781118445112.stat08237.
        Atchade, Y. F., G. O. Roberts, and J. S. Rosenthal (2011), 
            Towards optimal scaling of metropolis-coupled Markov chain Monte Carlo, Stat. Comput., 21(4), 555-568, doi:10.1007/s11222-010-9192-1.
        
    Attributes, public
    -------------------
        method: str
            "Metropolis_Hastings", necessary for the parent class 
        MH_step: MH_step Class
            Stepping determination method (a critical point of the methodology)
    
    Attributes, private
    -------------------
        __succes_rate: float
            Rate of success of Metropolis Hastings algorithm (should be between 0.2 and 0.45)
        config: MHConfig
            Immutable configuration of the MH run.
    
    Methods
    -------
        p_dist : LPMdist
            distribution of parameter values
            
    """   


    def __init__(self, config: MHConfig | None = None, **kwargs):
        """ Constructor: definition of  MH parameters 
        """
        # Parameters
        self.method="Metropolis_Hastings"
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
        self.prior = Prior(option=self.config.prior_option, typ=self.config.prior_type, prior_file=self.config.prior_file)
        # Results
        self.__success_rate = 0
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
        super(MetropolisHastings,self).__dict__.update(calib_basis.__dict__)


    def __param_inc(self, p0: List[float], lpm: Any, rng: np.random.Generator) -> List[float]:
        """ Increment parameters  
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
        """ posterior distribution 
        It is the logarithm of the posterior probability that is computed to avoid taking the exponential of the difference, 
        an hazardous operation for very small or very large numbers
        """
        log_proba = 0
        # If parameters are out of bounds, returns immediatly 0 
        if self.lpm.param_within_bounds_array(params) is False:
            return -math.inf, math.inf, []
        if self.config.likelihood:
            [objfunc,conc] = self.objective_function( params, data_conc, data_error, conc=True)
            log_proba = log_proba - 0.5 * objfunc #1
        else :
            objfunc = 0; conc = [1]
        if(self.prior.option):
            log_proba = log_proba + np.log(self.prior.evaluate(self.lpm,params)) 
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
        line=0
        for i in range(self.config.nstep):
            if i > self.config.burn_in * self.config.nstep and i % self.config.nskip == 0:
                line = line + 1
        # Number and name of columns that should be stored
        if self.config.likelihood:
            column = len(self.lpm.p) + 1 + len(self.cdata.names_dates()) + 1
            column_names = self.lpm.get_param_names() + \
                                ['obj_function'] + \
                                self.cdata.names_dates() + \
                                ['param_in_bounds']
        else:
            column = len(self.lpm.p) + 3
            column_names = self.lpm.get_param_names() + \
                                ['obj_function'] + \
                                ['conc'] + \
                                ['param_in_bounds']
        # Creation of table
        return np.zeros((line,column),dtype=float),column_names


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
        log_pn, obj_func_n, conc_n = self.__log_posterior_eval(params_n, data_conc, data_error)
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


    def __finalize_trajectory(self, traj: "MH_Trajectory", n: int, traj_options: TrajOptions) -> None:
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
        data_conc = self.cdata.cv.values[:,gp.CONCENTRATION]
        data_error = self.cdata.cv.values[:,gp.ERROR]
        # Initialization of stepping interval
        self.MH_step.prepare(self.lpm)
        # Trajectory monitoring
        traj = MH_Trajectory(self.lpm.p.keys(), self.config.nstep) if traj_options.monitor else None
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
        else:
            self.lpm.param_init()
        # Gets parameters in an array (compulsory for performance of the loop)
        params = self.lpm.get_parameters_to_array()
        # Value of the posterior distribution for initial set of parameters
        log_p, obj_func, conc = self.__log_posterior_eval(params, data_conc, data_error)
        return params, log_p, obj_func, conc


    def perform(self) -> LPM_dist.LpmDist:
        """
        Metropolis_Hastings Monte-Carlo Markov Chain Algorithm (MH MCMC)
            Main function
            Monitor run time necessary
        
        Modifies
        -------
            self.lpm.p_dist : LPMdist
                distribution of parameter values
                
        Returns
        -------
        lpm_results: LpmDist (class)
            lpm Parameters, objective function and concentration solutions
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
            if i > self.config.burn_in * self.config.nstep and i % self.config.nskip == 0:
                # Storage : everything relative to params and not params !!! (sources of errors to take params_n)
                array_results[line] = (
                    params
                    + [RMSE(obj_func, len(conc))]
                    + conc
                    + [1.0]
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
            self.prior_validation_stats = self.prior.validation_MH_prior(traj.path, self.lpm)
            
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
        except IndexError:
            raise ValueError(
                f"Cannot derive posterior directory from {file_path} "
                "(expected at least 4 parent levels)."
            )
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
        data['success_rate'] = self.__success_rate


