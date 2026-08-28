# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Manage the bounds and initial values of one LPM.

``ParameterManager`` connects the parameter order declared by
:class:`~pyages.lpm.core.lpm_base.LpmBase` with the validated schema loaded from
``<directory_lpm>/<model_name>/params.yaml``.  Names must match exactly;
bounds and initial values are finite floats, and bounds are inclusive.

Mapping checks require the complete parameter set.  Vector checks additionally
require constructor order, which remains canonical even when YAML order differs.
Parsing, caching, proposal steps, and priors belong to
:mod:`pyages.data_io.lpm_params`; this module keeps only the per-model snapshot
needed by ``LpmBase``.
"""

from __future__ import annotations

import math
from pathlib import Path

from pyages.data_io import lpm_params


class ParameterManager:
    """Manage validated bounds and initial values for one LPM definition.

    The instance keeps the constructor-declared parameter order and uses it
    for every list-shaped result.  Its validated schema is an immutable
    snapshot shared with the YAML loader.

    Parameters
    ----------
    model_name : str
        Registered LPM identifier and expected value of the YAML ``model``
        field.
    directory_lpm : str or pathlib.Path
        Root containing ``<model_name>/params.yaml``.
    parameter_names : list[str]
        Complete parameter-name sequence declared by the model.  Its order is
        the canonical calibration-vector order.

    Attributes
    ----------
    _p_min : dict[str, float]
        Validated lower bounds keyed by parameter name.
    _p_max : dict[str, float]
        Validated upper bounds keyed by parameter name.

    Raises
    ------
    FileNotFoundError
        If required parameter metadata is absent.
    ValueError
        If the YAML declaration is malformed or disagrees with
        ``parameter_names``.
    """

    def __init__(
        self, model_name: str, directory_lpm: str | Path, parameter_names: list[str]
    ) -> None:
        """
        Initialize parameter manager and load bounds.

        Parameters
        ----------
        model_name : str
            LPM model name (e.g., "ig", "exp")
        directory_lpm : str or pathlib.Path
            Directory containing LPM parameter files
        parameter_names : list[str]
            Names of parameters to manage
        """
        self._model_name = model_name
        self._directory_lpm = Path(directory_lpm)
        self._parameter_names = list(parameter_names)
        if not self._parameter_names or any(
            not isinstance(name, str) or not name for name in self._parameter_names
        ):
            raise ValueError("parameter_names must contain non-empty strings")
        if len(set(self._parameter_names)) != len(self._parameter_names):
            raise ValueError("parameter_names must not contain duplicates")
        self._p_min: dict[str, float] = {}
        self._p_max: dict[str, float] = {}
        self._schema: lpm_params.LPMParameterSchema
        self._load_bounds()

    def _params_file_path(self) -> Path:
        """Return the canonical YAML parameter file for this model."""
        return self._directory_lpm / self._model_name / "params.yaml"

    def _load_bounds(self) -> None:
        """Load shared parameter metadata and bind it to constructor names.

        Raises
        ------
        FileNotFoundError
            If the parameter file is missing.
        ValueError
            If the schema is malformed or inconsistent with the model
            constructor.
        """
        if not self._params_file_path().exists():
            raise FileNotFoundError(
                f"Missing params.yaml for {self._model_name} (required for bounds)."
            )
        schema = lpm_params.load_parameter_schema(
            self._model_name,
            self._directory_lpm,
        )
        expected = set(self._parameter_names)
        actual = set(schema.names)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"{self._model_name}: params.yaml names do not match the model "
                f"(missing={missing}, extra={extra})"
            )
        self._schema = schema
        self._p_min = {
            parameter.name: parameter.bounds[0] for parameter in schema.parameters
        }
        self._p_max = {
            parameter.name: parameter.bounds[1] for parameter in schema.parameters
        }

    def load_initial_values(self, target_params: dict[str, float]) -> None:
        """Replace target values with validated initial values from YAML.

        Parameters
        ----------
        target_params : dict[str, float]
            Dictionary to update with loaded values
        """
        if set(target_params) != set(self._parameter_names):
            missing = sorted(set(self._parameter_names) - set(target_params))
            extra = sorted(set(target_params) - set(self._parameter_names))
            raise ValueError(
                "target_params must match the managed parameters "
                f"(missing={missing}, extra={extra})"
            )
        initial_values = {
            parameter.name: parameter.init for parameter in self._schema.parameters
        }
        target_params.update(initial_values)

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
        if set(params) != set(self._parameter_names):
            return False
        for pname in self._parameter_names:
            try:
                value = float(params[pname])
            except (TypeError, ValueError):
                return False
            if not math.isfinite(value):
                return False
            if value < self._p_min[pname] or value > self._p_max[pname]:
                return False
        return True

    def param_within_bounds_array(
        self, params: list[float], param_order: list[str]
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
        if param_order != self._parameter_names:
            return False
        try:
            values = list(params)
        except TypeError:
            return False
        if len(values) != len(param_order):
            return False
        for value, pname in zip(values, param_order, strict=True):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return False
            if not math.isfinite(numeric_value):
                return False
            if numeric_value < self._p_min[pname] or numeric_value > self._p_max[pname]:
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
