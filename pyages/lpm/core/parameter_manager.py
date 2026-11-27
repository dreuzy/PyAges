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
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

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
        calibration_ranges = schema.calibration_ranges
        self._calibration_min = {
            name: calibration_range[0]
            for name, calibration_range in calibration_ranges.items()
        }
        self._calibration_max = {
            name: calibration_range[1]
            for name, calibration_range in calibration_ranges.items()
        }
        self._domains = schema.domains

    def initial_values(self) -> dict[str, float]:
        """Return YAML initial values in constructor-defined parameter order."""
        values_by_name = self._schema.initial_values
        return {name: values_by_name[name] for name in self._parameter_names}

    def _finite_parameter_values(
        self,
        params: Mapping[str, object],
    ) -> dict[str, float] | None:
        """Return one finite value per managed name, or ``None`` if invalid."""
        if not isinstance(params, Mapping) or set(params) != set(self._parameter_names):
            return None
        values: dict[str, float] = {}
        for name in self._parameter_names:
            try:
                value = float(cast(Any, params[name]))
            except (TypeError, ValueError):
                return None
            if not math.isfinite(value):
                return None
            values[name] = value
        return values

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
        values = self._finite_parameter_values(params)
        if values is None:
            return False
        for name, value in values.items():
            if (
                value < self._calibration_min[name]
                or value > self._calibration_max[name]
            ):
                return False
        return True

    def param_within_domain(self, params: dict[str, float]) -> bool:
        """Return whether a complete mapping belongs to the mathematical domain."""
        values = self._finite_parameter_values(params)
        return values is not None and all(
            self._domains[name].contains(value) for name, value in values.items()
        )

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

    def get_calibration_range(self, key: str) -> tuple[float, float]:
        """Return one parameter's inclusive operational calibration range."""
        return self._calibration_min[key], self._calibration_max[key]

    def get_calibration_ranges(self) -> dict[str, tuple[float, float]]:
        """Return calibration ranges in canonical parameter order."""
        return {
            name: self.get_calibration_range(name) for name in self._parameter_names
        }

    def get_domain(self, key: str) -> lpm_params.LPMParameterDomain:
        """Return one parameter's mathematical validity domain."""
        return self._domains[key]
