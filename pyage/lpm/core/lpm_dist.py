"""Container for calibrated LPM samples.

``LpmDist`` owns the sample table and coordinates model selection. Analysis,
plotting, and file output live in dedicated modules.
"""

from __future__ import annotations

import copy
from typing import Any, Sequence

import pandas as pd

from pyage.lpm.distribution_analysis import (
    add_moment_columns as _add_moment_columns,
)
from pyage.lpm.distribution_analysis import (
    append_target_statistics as _append_target_statistics,
)
from pyage.lpm.distribution_analysis import (
    compute_histograms as _compute_histograms,
)
from pyage.lpm.distribution_analysis import (
    select_models as _select_models,
)


class LpmDist:
    """Mutable table of model parameters, objectives, and concentrations."""

    def __init__(self, lpm: Any, c_names: Sequence[str]) -> None:
        self.__lpm_template = lpm
        self.__c_names = list(c_names)
        self.__dist = pd.DataFrame(columns=self._required_columns())

    @property
    def lpm_template(self) -> Any:
        """Model template used to interpret the parameter columns."""
        return self.__lpm_template

    @property
    def frame(self) -> pd.DataFrame:
        """Underlying mutable sample table."""
        return self.__dist

    def _required_columns(self) -> list[str]:
        return self.get_param_names() + ["obj_function"] + self.__c_names

    def get_param_names(self) -> list[str]:
        """Return model parameter names in their canonical order."""
        return list(self.__lpm_template.get_param_names())

    def get_concentration_names(self) -> list[str]:
        """Return stored concentration column names."""
        return list(self.__c_names)

    def validate(self) -> None:
        """Raise when a required sample column is missing."""
        missing = set(self._required_columns()).difference(self.__dist.columns)
        if missing:
            raise ValueError(f"Missing distribution columns: {sorted(missing)}")

    def best_row(self) -> pd.Series | None:
        """Return the row with the smallest finite objective value."""
        if self.__dist.empty:
            return None
        if "obj_function" not in self.__dist:
            return self.__dist.iloc[0].copy()
        objectives = pd.to_numeric(self.__dist["obj_function"], errors="coerce")
        if objectives.isna().all():
            return self.__dist.iloc[0].copy()
        return self.__dist.loc[objectives.idxmin()].copy()

    def append_sample(
        self,
        params: dict[str, float],
        obj_function: float = -1,
        param_in_bounds: bool | None = None,
        concentrations: Sequence[float] | None = None,
    ) -> None:
        """Append one simulation result."""
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

    def append_values(
        self,
        params: Sequence[float],
        obj_function: float = -1,
        param_in_bounds: bool | None = None,
        concentrations: Sequence[float] | None = None,
    ) -> None:
        """Append one simulation result using parameters in template order."""
        names = self.get_param_names()
        if len(params) != len(names):
            raise ValueError("params must match the model parameter count")
        self.append_sample(
            dict(zip(names, params, strict=True)),
            obj_function=obj_function,
            param_in_bounds=param_in_bounds,
            concentrations=concentrations,
        )

    def append(self, other: "LpmDist") -> None:
        """Append every sample from another compatible distribution."""
        if self.get_param_names() != other.get_param_names():
            raise ValueError("Cannot merge distributions with different parameters")
        self.__dist = pd.concat(
            [self.__dist, other.frame], ignore_index=True, sort=False
        )

    def fill_np_array(self, array_results, column_names: Sequence[str]) -> None:
        """Replace samples from a numeric array and its column names."""
        self.__dist = pd.DataFrame(data=array_results, columns=column_names)

    def best_model(self) -> Any | None:
        """Return a model copy configured from the best sample, if any."""
        row = self.best_row()
        if row is None:
            return None
        model = copy.deepcopy(self.__lpm_template)
        for name in model.p:
            model.p[name] = row[name]
        return model

    def select(self, count: int, resolution: int = 1000):
        """Select reproducible models and return models, PDFs, and moments."""
        return _select_models(
            self.__lpm_template,
            self.__dist,
            count,
            resolution,
        )

    def add_moments(self) -> "LpmDist":
        """Add one column per model moment to the sample table."""
        self.__dist = _add_moment_columns(self.__lpm_template, self.__dist)
        return self

    def histograms(self, bin_count: int = 100):
        """Compute a density histogram for every model parameter."""
        return _compute_histograms(self.__lpm_template, self.__dist, bin_count)

    def statistics(self) -> pd.DataFrame:
        """Return pandas descriptive statistics for stored numeric columns."""
        return self.__dist.describe()

    def append_target_statistics(self, lpm_target: Any, data: dict) -> None:
        """Append target-relative and descriptive statistics to ``data``."""
        _append_target_statistics(lpm_target, self.__dist, data)
