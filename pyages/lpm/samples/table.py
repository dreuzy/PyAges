# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Manage the results produced when calibrating a Lumped Parameter Model (LPM).

This module stores each tested parameter set, its objective-function value,
and its simulated tracer concentrations in one pandas table. It then provides
the operations needed to validate and combine these samples, recover the
best-fitting model, and calculate moments, histograms, and
descriptive statistics from the calibrated population.

Summary
-------
1. ``LpmSampleTable`` associates a model template with sampled results.
2. Parameter columns follow the canonical order declared by that template.
3. Objective values and named tracer concentrations share the same rows.
4. Samples can be appended as mappings or loaded from complete data frames.
5. Schema validation detects missing parameters, objectives, or concentrations.
6. The best finite objective identifies a representative calibrated model.
7. Returned models are deep copies, so the stored template remains reusable.
8. Reproducible model selection and moment calculation delegate to analysis helpers.
9. Histogram and descriptive-statistics methods summarize the sample population.
10. Plotting and tabular serialization remain in their dedicated modules.
"""

from __future__ import annotations

import copy
from typing import Any, Sequence

import numpy as np
import pandas as pd

from pyages.lpm.samples.analysis import (
    add_moment_columns as _add_moment_columns,
)
from pyages.lpm.samples.analysis import (
    append_reference_statistics as _append_reference_statistics,
)
from pyages.lpm.samples.analysis import (
    compute_parameter_histograms as _compute_parameter_histograms,
)
from pyages.lpm.samples.analysis import (
    select_model_realizations as _select_model_realizations,
)


class LpmSampleTable:
    """Manage a mutable table of calibration samples for one LPM family.

    Parameters
    ----------
    lpm : Any
        Model template defining parameter names, moments, and probability
        functions. The object is retained and must support the LPM interface.
    c_names : sequence of str
        Concentration column names stored alongside each parameter sample.

    Attributes
    ----------
    lpm_template : Any
        Model template used to interpret parameter columns.
    frame : pandas.DataFrame
        Mutable sample table. Its required columns are the model parameters,
        ``obj_function``, and the configured concentration names.

    Notes
    -----
    Parameter order is inherited from ``lpm.get_param_names()``. Methods that
    derive models or statistics assume that :meth:`validate` succeeds.
    """

    def __init__(self, lpm: Any, c_names: Sequence[str]) -> None:
        """Initialize an empty joint-sample table for one model template.

        Parameters
        ----------
        lpm : Any
            Model template implementing ``get_param_names()``.
        c_names : sequence of str
            Names of tracer-concentration columns expected in every complete
            sample table.
        """
        self.__lpm_template = lpm
        self.__c_names = list(c_names)
        self.__dist = pd.DataFrame(columns=self._required_columns())

    @property
    def lpm_template(self) -> Any:
        """Return the model template used to interpret parameter columns."""
        return self.__lpm_template

    @property
    def frame(self) -> pd.DataFrame:
        """Return the underlying mutable sample table.

        Notes
        -----
        The returned data frame is not a defensive copy. Mutating it changes
        the sample table and may invalidate the required-column contract.
        """
        return self.__dist

    def _required_columns(self) -> list[str]:
        """Return the minimum table schema in canonical column order."""
        return self.get_param_names() + ["obj_function"] + self.__c_names

    def _validate_frame(self, frame: pd.DataFrame) -> None:
        """Check one candidate frame against the sample-table schema."""
        duplicate_columns = frame.columns[frame.columns.duplicated()].unique()
        if len(duplicate_columns):
            raise ValueError(f"Duplicate sample columns: {sorted(duplicate_columns)}")
        missing = set(self._required_columns()).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing sample columns: {sorted(missing)}")

    def get_param_names(self) -> list[str]:
        """Return model parameter names in their canonical order.

        Returns
        -------
        list[str]
            A new list following the order defined by the model template.
        """
        return list(self.__lpm_template.get_param_names())

    def get_concentration_names(self) -> list[str]:
        """Return configured concentration column names.

        Returns
        -------
        list[str]
            A defensive copy of the names supplied at construction time.
        """
        return list(self.__c_names)

    def validate(self) -> None:
        """Check that the sample table contains every required column.

        Raises
        ------
        ValueError
            If a parameter, ``obj_function``, or configured concentration
            column is missing. Additional derived columns are allowed.
        """
        self._validate_frame(self.__dist)

    def best_row(self) -> pd.Series | None:
        """Return the sample with the smallest usable objective value.

        Returns
        -------
        pandas.Series or None
            A copy of the row minimizing ``obj_function``. ``None`` is
            returned for an empty table. If the objective column is absent or
            contains no finite numeric value, a copy of the first row is
            returned.
        """
        if self.__dist.empty:
            return None
        if "obj_function" not in self.__dist:
            return self.__dist.iloc[0].copy()
        objectives = pd.to_numeric(
            self.__dist["obj_function"], errors="coerce"
        ).to_numpy(dtype=float)
        finite_positions = np.flatnonzero(np.isfinite(objectives))
        if not len(finite_positions):
            return self.__dist.iloc[0].copy()
        best_position = finite_positions[np.argmin(objectives[finite_positions])]
        return self.__dist.iloc[int(best_position)].copy()

    def append_sample(
        self,
        params: dict[str, float],
        obj_function: float = -1,
        param_in_bounds: bool | None = None,
        concentrations: Sequence[float] | None = None,
    ) -> None:
        """Append one simulation result to the sample table.

        Parameters
        ----------
        params : dict[str, float]
            Parameter values keyed by every canonical template parameter.
        obj_function : float, default=-1
            Objective-function value associated with the simulation.
        param_in_bounds : bool or None, optional
            Optional bounds flag stored in a ``param_in_bounds`` column.
        concentrations : sequence of float or None, optional
            Concentrations ordered like :meth:`get_concentration_names`.

        Raises
        ------
        KeyError
            If ``params`` omits a required model parameter.
        ValueError
            If the number of concentrations does not match the configured
            concentration names.

        Notes
        -----
        Omitted optional values remain missing in the appended row.
        """
        row = {name: params[name] for name in self.get_param_names()}
        row["obj_function"] = obj_function
        if param_in_bounds is not None:
            row["param_in_bounds"] = param_in_bounds
        if concentrations is not None:
            if len(concentrations) != len(self.__c_names):
                raise ValueError(
                    "concentrations must match the configured concentration names"
                )
            row.update(zip(self.__c_names, concentrations, strict=True))
        new_sample = pd.DataFrame([row])
        if self.__dist.empty:
            columns = list(dict.fromkeys([*self.__dist.columns, *new_sample.columns]))
            self.__dist = new_sample.reindex(columns=columns)
        else:
            self.__dist = pd.concat([self.__dist, new_sample], ignore_index=True)

    def append(self, other: "LpmSampleTable") -> None:
        """Append every row from a schema-compatible sample table.

        Parameters
        ----------
        other : LpmSampleTable
            Source sample table. Its ordered parameter and concentration names
            must match those of this table; derived columns are merged
            by name.

        Raises
        ------
        ValueError
            If the parameter or concentration schemas differ, or if either
            table is missing required columns.
        """
        if self.get_param_names() != other.get_param_names():
            raise ValueError("Cannot merge sample tables with different parameters")
        if self.get_concentration_names() != other.get_concentration_names():
            raise ValueError("Cannot merge sample tables with different concentrations")
        self.validate()
        other.validate()
        self.__dist = pd.concat(
            [self.__dist, other.frame], ignore_index=True, sort=False
        )

    def replace_frame(self, frame: pd.DataFrame) -> None:
        """Replace all samples with a validated data frame.

        Parameters
        ----------
        frame : pandas.DataFrame
            Complete replacement table. Its index is normalized after schema
            validation.

        Notes
        -----
        Complete schema validation occurs before the existing samples are
        replaced.
        """
        candidate = frame.copy()
        self._validate_frame(candidate)
        self.__dist = candidate.reset_index(drop=True)

    def best_model(self) -> Any | None:
        """Build an independent model configured from the best sample.

        Returns
        -------
        Any or None
            A deep copy of :attr:`lpm_template` populated with the row returned
            by :meth:`best_row`, or ``None`` when there are no samples.

        Raises
        ------
        KeyError
            If the selected row lacks a required model parameter.
        """
        row = self.best_row()
        if row is None:
            return None
        model = copy.deepcopy(self.__lpm_template)
        model.set_param_from_array([row[name] for name in model.p])
        return model

    def select(
        self,
        count: int,
        resolution: int = 1000,
        rng: np.random.Generator | None = None,
    ) -> tuple[list[Any], pd.DataFrame, pd.DataFrame]:
        """Select reproducible samples and evaluate their PDFs and moments.

        Parameters
        ----------
        count : int
            Number of sample rows to draw reproducibly with replacement.
        resolution : int, default=1000
            Number of time points used to evaluate each probability density.
        rng : numpy.random.Generator or None, optional
            Random generator used to select rows. A generator seeded with
            ``12345`` is created when omitted.

        Returns
        -------
        models : list[Any]
            Independent model copies configured from the selected rows.
        pdfs : pandas.DataFrame
            Time coordinates and one probability-density column per draw.
        moments : pandas.DataFrame
            Model moments for each requested draw.

        Raises
        ------
        ValueError
            If ``count`` is negative or ``resolution`` is less than two.
        """
        return _select_model_realizations(
            self.__lpm_template,
            self.__dist,
            count,
            resolution,
            rng,
        )

    def add_moments(self) -> "LpmSampleTable":
        """Add or replace one column per model moment.

        Returns
        -------
        LpmSampleTable
            This sample table, enabling method chaining.

        Notes
        -----
        Existing moment columns are replaced, so repeated calls do not create
        duplicate columns. The model template is used transiently to evaluate
        each sample.
        """
        self.__dist = _add_moment_columns(self.__lpm_template, self.__dist)
        return self

    def histograms(self, bin_count: int = 100) -> dict[str, dict[str, Any]]:
        """Compute a density histogram for every model parameter.

        Parameters
        ----------
        bin_count : int, default=100
            Number of equal-width histogram bins.

        Returns
        -------
        dict[str, dict[str, numpy.ndarray]]
            Mapping from each parameter to its ``hist`` density values and
            ``bins`` edges.

        Raises
        ------
        ValueError
            If ``bin_count`` is not positive.
        """
        return _compute_parameter_histograms(
            self.__lpm_template, self.__dist, bin_count
        )

    def statistics(self) -> pd.DataFrame:
        """Return descriptive statistics for stored numeric columns.

        Returns
        -------
        pandas.DataFrame
            Count, mean, spread, extrema, and quartiles as produced by
            :meth:`pandas.DataFrame.describe`.
        """
        return self.__dist.describe()

    def append_target_statistics(self, lpm_target: Any, data: dict) -> None:
        """Append target-relative and descriptive statistics to a mapping.

        Parameters
        ----------
        lpm_target : Any
            Target model whose parameter values provide comparison baselines.
        data : dict
            Mutable output mapping. Generated scalar statistics are stored as
            one-element lists for subsequent tabular serialization.

        Notes
        -----
        This method mutates ``data`` in place and leaves the sample table
        unchanged.
        """
        _append_reference_statistics(lpm_target, self.__dist, data)


__all__ = ["LpmSampleTable"]
