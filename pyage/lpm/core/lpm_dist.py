"""Container for calibrated LPM samples.

``LpmDist`` owns the sample table and keeps the historical public methods used
by workflows. Analysis, plotting, and file output live in dedicated modules.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from pyage.lpm.distribution_analysis import (
    add_moment_columns,
    append_target_statistics,
    compute_histograms,
    select_models,
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
        """Underlying mutable sample table (kept mutable for compatibility)."""
        return self.__dist

    def dist(self) -> pd.DataFrame:
        """Return the sample table (compatibility alias for :attr:`frame`)."""
        return self.frame

    def compute_dist(self) -> pd.DataFrame:
        """Return the sample table (legacy compatibility alias)."""
        return self.frame

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

    def dist_append(
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
            row.update(zip(self.__c_names, concentrations))
        new_sample = pd.DataFrame([row])
        if self.__dist.empty:
            columns = list(dict.fromkeys([*self.__dist.columns, *new_sample.columns]))
            self.__dist = new_sample.reindex(columns=columns)
        else:
            self.__dist = pd.concat([self.__dist, new_sample], ignore_index=True)

    def dist_append_array(
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
        self.dist_append(
            dict(zip(names, params)),
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

    def get_best_lpm(self) -> tuple[bool, Any | None]:
        """Return a model copy configured from the best sample."""
        row = self.best_row()
        if row is None:
            return False, None
        model = copy.deepcopy(self.__lpm_template)
        for name in model.p:
            model.p[name] = row[name]
        return True, model

    def get_selection(
        self, lpm_number: int, time_span_mode: str, array_resolution: int = 1000
    ):
        """Select reproducible models and return models, PDFs, and moments."""
        return select_models(
            self.__lpm_template,
            self.__dist,
            lpm_number,
            time_span_mode,
            array_resolution,
        )

    def stats_distribution(self) -> "LpmDist":
        """Add one column per model moment to the sample table."""
        self.__dist = add_moment_columns(self.__lpm_template, self.__dist)
        return self

    def compute_histograms(self, nb_bins: int = 100):
        """Compute a density histogram for every model parameter."""
        return compute_histograms(self.__lpm_template, self.__dist, nb_bins)

    def compute_stats(self) -> pd.DataFrame:
        """Return pandas descriptive statistics for stored numeric columns."""
        return self.__dist.describe()

    def get_stats(self) -> pd.DataFrame:
        """Return descriptive statistics (compatibility alias)."""
        return self.compute_stats()

    def get_stats_line(self, lpm_target: Any, data: dict) -> None:
        """Append target-relative and descriptive statistics to ``data``."""
        append_target_statistics(lpm_target, self.__dist, data)

    def write_dist(self, file: str | Path) -> None:
        """Write the full sample table as TSV."""
        from pyage.data_io.lpm_distribution import write_distribution

        write_distribution(self, file)

    def write_histograms(self, file: str | Path) -> None:
        """Write one histogram table per parameter."""
        from pyage.data_io.lpm_distribution import write_histograms

        write_histograms(self, file)

    def write_stats(self, file: str | Path) -> None:
        """Write descriptive statistics as TSV."""
        from pyage.data_io.lpm_distribution import write_statistics

        write_statistics(self, file)

    def display_points_alone(self) -> None:
        """Plot the first two parameters."""
        from pyage.lpm.distribution_plotting import plot_points

        plot_points(self)

    def display_param_vs_param(self, keyx: str, keyy: str) -> None:
        """Plot one parameter against another."""
        from pyage.lpm.distribution_plotting import plot_parameter_pair

        plot_parameter_pair(self, keyx, keyy)

    def display_parameters_dist(
        self,
        self_method="",
        lpm_reference=None,
        bins=30,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
        display_text=False,
    ) -> None:
        """Plot posterior parameter distributions."""
        from pyage.lpm.distribution_plotting import display_parameter_distributions

        display_parameter_distributions(
            self,
            self_method,
            lpm_reference,
            bins,
            lpm_2nd,
            lpm_2nd_method,
            directory,
            display_text,
        )

    def display_parameters_dist_comp_apriori(
        self,
        lpm_reference=None,
        bins=30,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
        display_text=False,
        prior="",
    ) -> None:
        """Plot posterior parameter distributions against their priors."""
        from pyage.lpm.distribution_plotting import display_parameter_priors

        display_parameter_priors(
            self,
            lpm_reference,
            bins,
            lpm_2nd,
            lpm_2nd_method,
            directory,
            display_text,
            prior,
        )

    def display_concentrations_dist(
        self,
        self_method="",
        concentrations_reference=None,
        lpm_2nd=None,
        lpm_2nd_method="",
        directory=None,
    ) -> None:
        """Plot pairwise modeled concentration distributions."""
        from pyage.lpm.distribution_plotting import display_concentration_distributions

        display_concentration_distributions(
            self,
            self_method,
            concentrations_reference,
            lpm_2nd,
            lpm_2nd_method,
            directory,
        )
