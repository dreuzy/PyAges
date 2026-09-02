# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file loads and validates the YAML parameter definition for one LPM.
# Given the model name and canonical parameter order, it provides initial values,
# calibration ranges and mathematical domains and checks named mappings and
# vectors without silently reordering their values.

"""Manage mathematical domains, calibration ranges, and initial LPM values.

``ParameterManager`` connects the parameter order declared by
:class:`~pyages.lpm.core.lpm_base.LpmBase` with the validated schema loaded from
``<directory_lpm>/<model_name>/params.yaml``.  Names must match exactly;
calibration limits and initial values are finite floats, and ranges are inclusive.

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
    """Manage validated calibration ranges and initial values for one LPM.

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
    _calibration_min : dict[str, float]
        Validated lower calibration limits keyed by parameter name.
    _calibration_max : dict[str, float]
        Validated upper calibration limits keyed by parameter name.

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
        Initialize the parameter manager and load calibration ranges.

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
        self._calibration_min: dict[str, float] = {}
        self._calibration_max: dict[str, float] = {}
        self._domains: dict[str, lpm_params.LPMParameterDomain] = {}
        self._schema: lpm_params.LPMParameterSchema
        self._load_parameter_metadata()

    def _params_file_path(self) -> Path:
        """Return the canonical YAML parameter file for this model."""
        return self._directory_lpm / self._model_name / "params.yaml"

    def _load_parameter_metadata(self) -> None:
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
                f"Missing params.yaml for {self._model_name} "
                "(required for calibration ranges)."
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
        self._calibration_min = {
            parameter.name: parameter.calibration_range[0]
            for parameter in schema.parameters
        }
        self._calibration_max = {
            parameter.name: parameter.calibration_range[1]
            for parameter in schema.parameters
        }
        self._domains = {
            parameter.name: parameter.domain for parameter in schema.parameters
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

    def param_within_calibration_range(self, params: dict[str, float]) -> bool:
        """Test whether parameters are within their calibration ranges.

        Parameters
        ----------
        params : dict[str, float]
            Parameters to test

        Returns
        -------
        bool
            True if every parameter is within its calibration range.
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
            if (
                value < self._calibration_min[pname]
                or value > self._calibration_max[pname]
            ):
                return False
        return True

    def param_within_bounds(self, params: dict[str, float]) -> bool:
        """Return the legacy alias for :meth:`param_within_calibration_range`."""
        return self.param_within_calibration_range(params)

    def param_within_domain(self, params: dict[str, float]) -> bool:
        """Return whether a complete mapping belongs to the mathematical domain."""
        if set(params) != set(self._parameter_names):
            return False
        for name in self._parameter_names:
            try:
                value = float(params[name])
            except (TypeError, ValueError):
                return False
            if not self._domains[name].contains(value):
                return False
        return True

    def param_within_calibration_range_array(
        self, params: list[float], param_order: list[str]
    ) -> bool:
        """Test whether an ordered vector is within its calibration ranges.

        Parameters
        ----------
        params : list[float]
            Parameter values in order
        param_order : list[str]
            Parameter names in same order as params

        Returns
        -------
        bool
            True if every parameter is within its calibration range.
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
            if (
                numeric_value < self._calibration_min[pname]
                or numeric_value > self._calibration_max[pname]
            ):
                return False
        return True

    def param_within_bounds_array(
        self, params: list[float], param_order: list[str]
    ) -> bool:
        """Return the legacy alias for the calibration-range vector check."""
        return self.param_within_calibration_range_array(params, param_order)

    def param_within_domain_array(
        self, params: list[float], param_order: list[str]
    ) -> bool:
        """Return whether an ordered vector belongs to the mathematical domain."""
        if param_order != self._parameter_names:
            return False
        try:
            values = list(params)
        except TypeError:
            return False
        if len(values) != len(param_order):
            return False
        for value, name in zip(values, param_order, strict=True):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return False
            if not self._domains[name].contains(numeric_value):
                return False
        return True

    def get_calibration_range_width(self, param_name: str) -> float:
        """Return the width of one parameter's calibration range.

        Parameters
        ----------
        param_name : str
            Name of the parameter

        Returns
        -------
        float
            Range of parameter values
        """
        lower, upper = self.get_calibration_range(param_name)
        return upper - lower

    def get_param_range(self, param_name: str) -> float:
        """Return the legacy alias for :meth:`get_calibration_range_width`."""
        return self.get_calibration_range_width(param_name)

    def get_calibration_range(self, key: str) -> tuple[float, float]:
        """Return one parameter's inclusive operational calibration range."""
        return self._calibration_min[key], self._calibration_max[key]

    def get_calibration_ranges(self) -> dict[str, tuple[float, float]]:
        """Return calibration ranges in canonical parameter order."""
        return {
            name: self.get_calibration_range(name) for name in self._parameter_names
        }

    def get_param_interval(self) -> tuple[list[float], list[float]]:
        """Return the legacy pair of lower and upper calibration-limit lists.

        Returns
        -------
        tuple[list[float], list[float]]
            Lower and upper calibration limits in canonical parameter order.
        """
        ranges = tuple(self.get_calibration_ranges().values())
        pmin = [interval[0] for interval in ranges]
        pmax = [interval[1] for interval in ranges]
        return pmin, pmax

    def get_domain(self, key: str) -> lpm_params.LPMParameterDomain:
        """Return one parameter's mathematical validity domain."""
        return self._domains[key]

    def get_p_max(self, key: str) -> float:
        """Return the legacy upper calibration limit for one parameter."""
        return self.get_calibration_range(key)[1]

    def get_p_min(self, key: str) -> float:
        """Return the legacy lower calibration limit for one parameter."""
        return self.get_calibration_range(key)[0]
