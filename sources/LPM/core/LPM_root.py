# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 09:29:57 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Base classes and utilities for Lumped Parameter Models (LPM).
Defines the common interface and shared numerical helpers used by
specific LPM implementations (pdf/cdf, moments, parameter handling,
and optimization utilities). Concrete models inherit from this root
to ensure consistent behavior across calibration and convolution
workflows.
"""

from __future__ import annotations

import abc
import copy
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import os
import pandas as pd
from scipy import integrate
from scipy import optimize
from pathlib import Path
       

class LPM(abc.ABC):
    """  
    Lumped Parameter Model, pure virtual class

    Inheritance
    -----------
    LPMDist : class
        Class containing distribution of values of LPM

    Attributes, public
    ----------
    name : str
        name of LPM 
    p : dictionary
        p["parameter name"] = parameter values 

    Attributes, private
    ----------
    __u : dictionary 
        __u["parameter name"] = parameter unit
    __p_min : dictionary
        __p_min["parameter name"] = parameter lower bound 
        Loaded from external file 
    __p_max : dictionary
        __p_max["parameter name"] = parameter higher bound
        Loaded from external file 
    _directory_lpm : str
        directory of the parameters necessary for the models 
    
    Methods (defined in this class)
    -------
    param_within_bounds(self,param)
        Test whether parameters are in the [lower,higher] intervals
    random_uniform(self,rng=None)
        Random uniform generation of lpm within parameter range defined by get_param_interval(), modifies self
    set_param_from_array(self, param)
        Sets parameters from array with same order required
    get_parameters_to_array(self)
        Gets parameters to an array (same order as in the dictionary)
    __moment_k(self,k)
        Computes and returns the moment of order k
    __support_range(self)
        define typical [min,max] interval on which the pdf is defined
        
    Methods-Pure Virtual (defined in the daughter classes, required)
    --------------------
    pdf(self,t)
        probability density function: should be defined in daughter class

    Methods-Virtual (defined in the daughter classes, when relevant, template alternative given in mother class)
    ---------------
    cdf(self,t)
        cumulative density function 
    cdf_inv(self,p)
        inverse of the cumulative density function
    mean(self):
        Returns mean of distribution
    std(self):
        Returns std of distribution
    
    """
    
    def __init__(
        self,
        name: str,
        parameter_values: dict[str, float],
        parameter_units: dict[str, str],
        directory_lpm: str
    ) -> None:
        """
        Constructor

        Parameters
        ---------
        name: str
            LPM name
        parameter_values: dict[str, float]
            parameter_values["parameter name"] = parameter values
        parameter_units : dict[str, str]
            parameter_units["parameter name"] = parameter unit
        directory_lpm : str
            directory of the parameters necessary for the models
        """
        # Name of LPM (e.g. IG, EXP)
        self.name = name
        # Parameter Values
        self.p = parameter_values     
        # Parameter Units 
        self.__u = parameter_units  
        # Bounds of distribution parameters
        self.__p_min = {}
        self.__p_max = {}
        if directory_lpm is None:
            raise ValueError("directory_lpm must be provided, got None")
        self._directory_lpm = directory_lpm
        # Load lower and higher bounds 
        self.__load_bounds()


    @abc.abstractmethod


    def pdf(self, t: npt.ArrayLike) -> npt.ArrayLike:
        """
        Probability Density Function
        Should be defined in the daughter class

        Parameters
        ---------
        t : scalar or array
            Time values

        Returns
        -------
        pdf: scalar or array (same size as input t)
            Probability density function
        """
        pass

        
    def __moment_k(self, k: int, n_points: int = 1000) -> float:
        """
        Returns moment k of distribution (discretized)

        Parameters
        ---------
        k : int
            Order of the moment
        n_points : int
            Number of discretization points (default: 1000)
        """
        tmin, tmax = self.__support_range()
        t = np.linspace(tmin, tmax, n_points)
        pdf = self.pdf(t)
        return integrate.simpson(t**k * pdf, x=t)

    
    def mean(self) -> float:
        """Return mean of distribution."""
        return self.__moment_k(1)


    def std(self) -> float:
        """Return standard deviation of distribution."""
        return np.sqrt(self.__moment_k(2) - self.__moment_k(1)**2)
        
        
    def random_uniform(self, rng: np.random.Generator | None = None) -> None:
        """
        Random uniform generation of lpm
            Modifies self with uniform random generation of parameters
            Parameters are drawn from get_param_interval()
        """
        pmin, pmax = self.get_param_interval()
        if rng is None:
            rng = np.random.default_rng()
        param = [pmin[i] + (pmax[i] - pmin[i]) * rng.random() for i in range(len(pmin))]
        self.set_param_from_array(param)


    def param_init(self) -> list[float]:
        """
        Initialization parameters in an array
            Does not change the parameters in self

        Returns
        -------
        list[float]
            Parameters in an array format
        """
        lpm_temp = copy.deepcopy(self)
        lpm_temp.load_param_values(self.lpm_parameter_file("simplex_init.txt"))
        return lpm_temp.get_parameters_to_array()


    def lpm_parameter_file(self, file_name: str) -> str:
        """
        Directory + File where the lpm parameters are defined

        Parameters
        ---------
        file_name : str
            File name

        Returns
        -------
        str
            Full directory + file name
        """
        return os.path.join(self._directory_lpm, self.name, file_name)


    def __load_params_yaml(self) -> dict | None:
        """Load YAML parameters if present in the LPM directory."""
        from data_io import lpm_params

        path = self.lpm_parameter_file("params.yaml")
        if not hasattr(LPM, "_PARAMS_CACHE"):
            LPM._PARAMS_CACHE = {}
        cache = LPM._PARAMS_CACHE
        if path in cache:
            return cache[path]
        if not os.path.exists(path):
            return None
        data = lpm_params.load_params(self.name, Path(self._directory_lpm))
        cache[path] = data
        return data
        
    
    def load_param_values(self,file_name):
        """ 
        Loads parameter values from a file
        File structure
            param_name,param_value,unit
        File example 
            mu1,5,year
            mu2,10,year
            rate,0.25,-
        
        Parameters
        --------
        file_name : str
            Name of the file
        
        Returns
        -------
        dictionary
            p["param_name"]=param_value
        """
        if os.path.basename(file_name) == "simplex_init.txt":
            params_yaml = self.__load_params_yaml()
            if not params_yaml or "parameters" not in params_yaml:
                raise FileNotFoundError(
                    f"Missing params.yaml for {self.name} (required for simplex init)."
                )
            for param in params_yaml["parameters"]:
                if "init" in param:
                    self.p[param["name"]] = param["init"]
            return
        raise FileNotFoundError(
            f"Legacy parameter file not supported: {file_name}. "
            f"Use params.yaml in {self.lpm_parameter_file('params.yaml')}."
        )
        
    
    def __load_bounds(self):
        """ 
        Loads lower and higher bounds of each of the distribution parameter 
            From file called bounds.txt in the LPM directory
        File structure
            param_name,lower_bound,higher_bound,unit
        File example 
            mu1,0,100,year
            mu2,0,100,year
            rate,0,1,-
        """
        params_yaml = self.__load_params_yaml()
        if not params_yaml or "parameters" not in params_yaml:
            raise FileNotFoundError(
                f"Missing params.yaml for {self.name} (required for bounds)."
            )
        for param in params_yaml["parameters"]:
            bounds = param.get("bounds")
            if bounds and len(bounds) == 2:
                self.__p_min[param["name"]] = bounds[0]
                self.__p_max[param["name"]] = bounds[1]
        
        
    def param_within_bounds(self, params: dict[str, float]) -> bool:
        """
        Test whether parameters are within the defined bounds

        Parameters
        ---------
        params: dict[str, float]
            params to be tested, same structure as self.p

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        for pname in params:
            val = params[pname]
            if val < self.__p_min[pname] or val > self.__p_max[pname]:
                return False
        return True


    def param_within_bounds_array(self, params: list[float]) -> bool:
        """
        Test whether parameters are within the defined bounds

        Parameters
        ---------
        params: list[float]
            params to be tested
            parameters should be in the same order as in the dictionary self.p

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        for ikey, pname in enumerate(self.p):
            val = params[ikey]
            if val < self.__p_min[pname] or val > self.__p_max[pname]:
                return False
        return True

    
    def cdf(self, t: npt.ArrayLike) -> list[float]:
        """
        Cumulative Density Function
            Should be defined in the daughter class
            Can be called here as the integration of the pdf
            Function does not critically intervene in the code, mostly plotting purposes

        Parameters
        ---------
        t : array-like
            Time values

        Returns
        -------
        list[float]
            Cumulative density function values
        """
        val = [0.0] * len(t)
        for i in range(len(t)):
            val[i] = integrate.quadrature(self.pdf, 0.0, t[i])[0]
        return val


    def _cdf_minus_p(self, t: float, p: float) -> float:
        """Instrumental function for cdf_inv"""
        return (self.cdf(t) - p) ** 2


    def cdf_inv(self, p: float) -> float:
        """
        Inverse of the Cumulative Density Function, t=cdf^-1(p)
            Useful for the computation of quantiles
            Should be defined in the daughter class

        Parameters
        ---------
        p : float
            probability

        Returns
        -------
        float
            time corresponding to cdf^-1(p)
        """
        t0 = 10
        res = optimize.root(self._cdf_minus_p, t0, args=(p), method='hybr', jac=None, tol=None, callback=None, options=None)
        return res.x[0]
    
    
    def set_param_from_array(self, param: list[float]) -> None:
        """Set parameters from array to dictionary."""
        for k, key in enumerate(self.p):
            self.p[key] = param[k]


    def get_parameters_to_array(self) -> list[float]:
        """Get parameters as array."""
        return list(self.p.values())


    def get_param_names(self) -> list[str]:
        """Return parameter names."""
        return list(self.p.keys())


    def get_param_range(self, param_name: str) -> float:
        """
        Gets the range of parameters

        Parameters
        ---------
        param_name: str
            name of parameter

        Returns
        -------
        float
            Range of parameter values
        """
        return self.__p_max[param_name] - self.__p_min[param_name]


    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """
        Gets the interval of parameters

        Returns
        -------
        tuple[list[float], list[float]]
            (pmin, pmax) - lower and higher bounds
        """
        pmin = list(self.__p_min.values())
        pmax = list(self.__p_max.values())
        return pmin, pmax


    def get_p_max(self, key: str) -> float:
        """Return upper bound for parameter."""
        return self.__p_max[key]


    def get_p_min(self, key: str) -> float:
        """Return lower bound for parameter."""
        return self.__p_min[key]
    
    
    def display(self, display_options: Any) -> None:
        """Display LPM."""
        if display_options.text:
            print("LPM type:", self.name)
            print("Parameters:")
            for key in self.p.keys():
                print("\t", key, "\t=", self.p[key], self.__u[key])


    def __support_range(self) -> tuple[float, float]:
        """
        Defines Support Time Range
            Specific to the distribution itself and to its parameters

        Returns
        -------
        tuple[float, float]
            (tmin, tmax) - minimum and maximum time of support range
        """
        tmin = 0
        tmax = 1.2 * self.cdf_inv(0.98)
        return tmin, tmax


    def discret_pdf_cdf(self, type_pc: str, n: int) -> tuple[np.ndarray, npt.ArrayLike]:
        """
        Discretization of pdf or cdf
            discretization in n steps in the range defined by the __support_range function

        Parameters
        ---------
        type_pc : str
            "pdf" or "cdf"
        n : int
            number of discretization steps

        Returns
        -------
        tuple[np.ndarray, array-like]
            (t, values) - discrete times and pdf/cdf values
        """
        tmin, tmax = self.__support_range()
        t = np.linspace(tmin, tmax, n)
        if type_pc == 'pdf':
            values = self.pdf(t)
        elif type_pc == 'cdf':
            values = self.cdf(t)
        else:
            raise ValueError(f"type_pc must be 'pdf' or 'cdf', got '{type_pc}'")
        return t, values


    def plot(self, type_pc: str, display_options: Any) -> None:
        """
        Plots distribution (pdf or cdf)

        Parameters
        ---------
        type_pc : str
            "pdf" or "cdf"
        display_options : display_options
            display configuration
        """
        if display_options.figure:
            t, values = self.discret_pdf_cdf(type_pc, 1000)
            plt.figure()
            plt.xlabel('t', fontsize=16, fontweight='bold')
            plt.xticks(fontsize=14)
            plt.ylabel('f(t)', fontsize=14, fontweight='bold')
            plt.yticks(fontsize=14)
            plt.title(type_pc + " of " + self.name, fontsize=22, fontweight='bold')
            plt.grid(True)
            if len(t) != len(values):
                raise ValueError(f"Dimension mismatch: len(t)={len(t)} != len(values)={len(values)}")
            plt.plot(t, values, 'r', label=self.name)
            plt.xlim((0, max(t)))
            if max(t) == 0:
                print(max(t))
            if max(values) <= 0:
                ylim = 1
            else:
                ylim = max(values) * 1.1
            if not np.isnan(ylim) and not np.isinf(ylim):
                plt.ylim((0, ylim))
            display_options.figure_close_fx(self.name + "_" + type_pc)
    
    
    def display_parameters(self, lpm_reference: LPM | None = None) -> None:
        """Display values of LPM parameters."""
        if lpm_reference is None:
            for key in self.p:
                print(key, '\t', '%.2f' % self.p[key])
        else:
            for key in self.p:
                print(key, '\t', 'target ', '%.2f' % lpm_reference.p[key],
                      '\t calibrated', '%.2f' % self.p[key], '\t',
                      'difference rate', '%.1e' % (self.p[key] / lpm_reference.p[key] - 1))


    def display_pdf_cdf(self, display_options: Any) -> None:
        """Check consistency of distribution."""
        self.display(display_options)
        self.plot('pdf', display_options)
        self.plot('cdf', display_options)
        
        
    def write_name(self, file: Any) -> None:
        """Write LPM name to file."""
        file.write("lpm\t" + self.name + "\n")


    def write(self, file: str | Any, open_file: bool = False) -> None:
        """
        Write LPM name and values to file.

        Parameters
        ---------
        file: str or file object
            If open_file is True: file path as string
            If open_file is False: opened file object
        open_file: bool
            Whether to open the file (True) or use existing file object (False)
        """
        if open_file:
            file = open(file, "w")
        self.write_name(file)
        for key in self.p:
            file.write(key + '\t' + str(self.p[key]) + '\t' + str(self.__u[key]) + '\n')
        if open_file:
            file.close()


    def load_lpm_from_dist(
        self,
        dist: pd.DataFrame,
        option: str = "line",
        rng: np.random.Generator | None = None,
        line_no: int = 0
    ) -> tuple[bool, dict[str, int]]:
        """
        Loads parameter values from distribution file

        Parameters
        ---------
        dist : pd.DataFrame
            distribution of parameter values
        option : str
            - "random_line" : all parameters from the same random line
            - "line"        : all parameters from the specified line (line_no)
            - "random_each" : each parameter from its own random line
            - otherwise     : all parameters from first line
        rng : np.random.Generator or None
            random number generator
        line_no : int
            index of the line to use if option == "line"

        Returns
        -------
        tuple[bool, dict[str, int]]
            (success, chosen_lines) - success flag and dict of param -> line index
        """
        if len(dist.index) == 0:
            return (False, {})

        if rng is None:
            rng = np.random

        chosen_lines: dict[str, int] = {}

        if option == "random_line":
            line = rng.integers(len(dist.index)) if hasattr(rng, "integers") else rng.randint(len(dist.index))
            for key in self.p.keys():
                self.p[key] = dist[key].iloc[line]
                chosen_lines[key] = line

        elif option == "line":
            if line_no >= len(dist.index):
                line_no = len(dist.index) - 1
            for key in self.p.keys():
                self.p[key] = dist[key].iloc[line_no]
                chosen_lines[key] = line_no

        elif option == "random_each":
            for key in self.p.keys():
                line = rng.integers(len(dist.index)) if hasattr(rng, "integers") else rng.randint(len(dist.index))
                self.p[key] = dist[key].iloc[line]
                chosen_lines[key] = line

        else:
            for key in self.p.keys():
                self.p[key] = dist[key].iloc[0]
                chosen_lines[key] = 0

        return (True, chosen_lines)


    def moments_name(self) -> list[str]:
        """Return moment names."""
        return ['mean', 'std', 'quart10', 'quart25', 'median', 'quart75', 'quart90']


    def moments(self) -> list[float]:
        """Compute statistical characteristics of the distribution."""
        return [
            self.mean(), self.std(),
            self.cdf_inv(0.10), self.cdf_inv(0.25), self.cdf_inv(0.5),
            self.cdf_inv(0.75), self.cdf_inv(0.90)
        ]


    def display_moments(self) -> None:
        """Display computed moments."""
        print("\nmoments")
        names = self.moments_name()
        values = self.moments()
        for i in range(len(names)):
            print(names[i], "", values[i])
        print("\n")


    def output_dataframe(self) -> pd.DataFrame:
        """Output model as dataframe."""
        data: dict[str, Any] = {'LPM_name': self.name}
        for key in self.p:
            data[key] = self.p[key]
        return pd.DataFrame(data, index=[0])
        


