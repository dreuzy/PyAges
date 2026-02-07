# -*- coding: utf-8 -*-
"""
Parameter management for LPM models.

Handles loading, validation, and access to parameter bounds and values
from YAML configuration files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class ParameterManager:
    """
    Manages LPM parameter bounds, loading, and validation.

    Attributes
    ----------
    _p_min : dict[str, float]
        Lower bounds for each parameter
    _p_max : dict[str, float]
        Upper bounds for each parameter
    """

    # Class-level cache shared across all instances to avoid repeated YAML loads.
    _PARAMS_CACHE: dict[str, dict | None] = {}

    def __init__(
        self,
        model_name: str,
        directory_lpm: str,
        parameter_names: list[str]
    ) -> None:
        """
        Initialize parameter manager and load bounds.

        Parameters
        ----------
        model_name : str
            LPM model name (e.g., "ig", "exp")
        directory_lpm : str
            Directory containing LPM parameter files
        parameter_names : list[str]
            Names of parameters to manage
        """
        self._model_name = model_name
        self._directory_lpm = directory_lpm
        self._parameter_names = parameter_names
        self._p_min: dict[str, float] = {}
        self._p_max: dict[str, float] = {}
        self._load_bounds()

    def _params_file_path(self, file_name: str = "params.yaml") -> str:
        """
        Return the full path to a parameter file for this model.
        """
        return os.path.join(self._directory_lpm, self._model_name, file_name)

    def _load_params_yaml(self) -> dict | None:
        """
        Load YAML parameters if present, with caching.

        Returns
        -------
        dict | None
            Parsed YAML content or None when missing.
        """
        from pyage.data_io import lpm_params

        path = self._params_file_path()
        if path in ParameterManager._PARAMS_CACHE:
            return ParameterManager._PARAMS_CACHE[path]
        if not os.path.exists(path):
            return None
        data = lpm_params.load_params(self._model_name, Path(self._directory_lpm))
        ParameterManager._PARAMS_CACHE[path] = data
        return data

    def _load_bounds(self) -> None:
        """
        Load lower and upper bounds from params.yaml.
        """
        params_yaml = self._load_params_yaml()
        if not params_yaml or "parameters" not in params_yaml:
            raise FileNotFoundError(
                f"Missing params.yaml for {self._model_name} (required for bounds)."
            )
        for param in params_yaml["parameters"]:
            bounds = param.get("bounds")
            if bounds and len(bounds) == 2:
                self._p_min[param["name"]] = bounds[0]
                self._p_max[param["name"]] = bounds[1]

    def load_param_values(
        self,
        file_name: str,
        target_params: dict[str, float]
    ) -> None:
        """
        Load parameter values from file into target dict.

        Parameters
        ----------
        file_name : str
            Name of the parameter file
        target_params : dict[str, float]
            Dictionary to update with loaded values
        """
        if os.path.basename(file_name) == "simplex_init.txt":
            params_yaml = self._load_params_yaml()
            if not params_yaml or "parameters" not in params_yaml:
                raise FileNotFoundError(
                    f"Missing params.yaml for {self._model_name} (required for simplex init)."
                )
            for param in params_yaml["parameters"]:
                if "init" in param:
                    target_params[param["name"]] = param["init"]
            return
        raise FileNotFoundError(
            f"Legacy parameter file not supported: {file_name}. "
            f"Use params.yaml in {self._params_file_path()}."
        )

    def param_within_bounds(self, params: dict[str, float]) -> bool:
        """
        Test whether parameters are within defined bounds.

        Parameters
        ----------
        params : dict[str, float]
            Parameters to test

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        for pname in params:
            val = params[pname]
            if val < self._p_min[pname] or val > self._p_max[pname]:
                return False
        return True

    def param_within_bounds_array(
        self,
        params: list[float],
        param_order: list[str]
    ) -> bool:
        """
        Test whether array parameters are within bounds.

        Parameters
        ----------
        params : list[float]
            Parameter values in order
        param_order : list[str]
            Parameter names in same order as params

        Returns
        -------
        bool
            True if all parameters are within bounds
        """
        for ikey, pname in enumerate(param_order):
            val = params[ikey]
            if val < self._p_min[pname] or val > self._p_max[pname]:
                return False
        return True

    def get_param_range(self, param_name: str) -> float:
        """
        Return the range (max - min) for a parameter.

        Parameters
        ----------
        param_name : str
            Name of the parameter

        Returns
        -------
        float
            Range of parameter values
        """
        return self._p_max[param_name] - self._p_min[param_name]

    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """
        Return (pmin_list, pmax_list) for all parameters.

        Returns
        -------
        tuple[list[float], list[float]]
            (pmin, pmax) - lower and upper bounds
        """
        pmin = [self._p_min[name] for name in self._parameter_names]
        pmax = [self._p_max[name] for name in self._parameter_names]
        return pmin, pmax

    def get_p_max(self, key: str) -> float:
        """Return upper bound for parameter."""
        return self._p_max[key]

    def get_p_min(self, key: str) -> float:
        """Return lower bound for parameter."""
        return self._p_min[key]
