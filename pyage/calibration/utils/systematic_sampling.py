"""Systematic exploration of an LPM parameter space."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from pyage.calibration.utils.parameter_grid import ParameterGrid
from pyage.calibration.utils.sampling_plotting import (
    plot_parameter_grid,
    plot_reachable_concentrations,
)
from pyage.config.runtime import DisplayOptions
from pyage.convolution.convolution_tracers import ConvolutionTracers
from pyage.lpm.lpm_build import lpm_build

if TYPE_CHECKING:
    from pyage.concentrations.concentrations import Concentrations


class SystematicSampling:
    """Evaluate concentrations and an objective on a regular parameter grid."""

    def __init__(
        self,
        lpm_name: str,
        tracer_names: Iterable[str],
        date: float | Iterable[float] = 2010,
        sample_count: int = 1000,
        observations: Concentrations | None = None,
        explore_objective: bool = True,
        explore_reachable: bool = True,
        display_options: DisplayOptions | None = None,
        lpm_directory: str | Path | None = None,
        tracer_data_directory: str | Path | None = None,
    ) -> None:
        self._tracers = ConvolutionTracers(
            names=tracer_names,
            date=date,
            tracer_data_dir=tracer_data_directory,
        )
        self._lpm = lpm_build(lpm_name, directory_lpm=lpm_directory)
        self._target_size = sample_count
        self._date = date
        self._observations = observations
        self.display = display_options or DisplayOptions()
        self.display_objective = bool(explore_objective)
        self.display_reachable = bool(explore_reachable)

        minima, maxima = self._lpm.get_param_interval()
        self._grid = ParameterGrid(
            minima,
            maxima,
            sample_count,
            tuple(self._lpm.p),
        )
        self._concentrations: pd.DataFrame | None = None
        self._objective: pd.DataFrame | None = None

    def compute_concentrations(self) -> pd.DataFrame:
        """Evaluate every tracer for every parameter combination."""
        points = self._grid.points()
        columns = self._tracers.element_names_dates()
        values = np.zeros((len(points), len(columns)))
        self._tracers.prepare(self._lpm)
        for index, parameters in enumerate(points):
            self._lpm.set_param_from_array(parameters)
            values[index, :] = self._tracers.convolve(
                self._lpm,
                apply_age_correction=True,
            )
        self._concentrations = pd.DataFrame(values, columns=columns)
        self._objective = None
        return self.concentrations_frame()

    def _require_concentrations(self) -> pd.DataFrame:
        if self._concentrations is None:
            raise RuntimeError("compute_concentrations() must be called first")
        return self._concentrations

    def display_concentrations_with_data(self, imax=10) -> None:
        """Plot pairwise projections of the reachable concentrations."""
        plot_reachable_concentrations(
            self._require_concentrations(),
            self.display,
            observations=self._observations,
            maximum=imax,
        )

    def output(self) -> None:
        """Write the sampling metadata and reachable concentrations."""
        if self.display.directory is None:
            raise ValueError("display.directory is required to write sampling output")
        output_directory = Path(self.display.directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        with (output_directory / "parameters.txt").open(
            "w", encoding="utf-8"
        ) as stream:
            stream.write(f"date\t{self._date}\n")
            self._lpm.write_name(stream)
            self._tracers.write_name(stream)
            stream.write(f"nmodels\t{self._target_size}\n")
        self._require_concentrations().to_csv(
            output_directory / "c_reach.txt",
            sep="\t",
        )

    def objective_function_build(self) -> pd.DataFrame:
        """Compute half the log squared normalized residual on the grid."""
        if self._observations is None:
            raise RuntimeError("Observation data is required to build the objective")
        modeled = self._require_concentrations()
        observed = self._observations.cv_key_name_date().reset_index(drop=True)
        if len(observed) != len(modeled.columns):
            raise ValueError("Observation and model dimensions do not match")

        observed_names = observed["element"].astype(str).tolist()
        modeled_names = [str(name) for name in modeled.columns]
        if observed_names != modeled_names:
            raise ValueError(
                "Observation and model tracer order differs: "
                f"{observed_names} != {modeled_names}"
            )
        errors = observed["error"].to_numpy(dtype=float)
        if np.any(errors <= 0.0) or not np.all(np.isfinite(errors)):
            raise ValueError("Observation errors must be finite and strictly positive")

        values = observed["concentration"].to_numpy(dtype=float)
        residuals = (modeled.to_numpy(dtype=float) - values) / errors
        squared_norm = np.square(residuals).sum(axis=1)
        half_log_norm = 0.5 * np.log(np.maximum(squared_norm, np.finfo(float).tiny))
        data = np.column_stack((self._grid.points(), half_log_norm))
        self._objective = pd.DataFrame(
            data,
            columns=[*self._grid.names, "log-ojf"],
        )
        return self.objective_function_frame()

    def objective_function_display(self, lpm_results=None) -> None:
        """Plot the gridded objective values when figures are enabled."""
        objective = self._require_objective()
        values = self._grid.reshape(objective["log-ojf"].to_numpy())
        plot_parameter_grid(
            self._grid,
            values,
            self.display,
            name=f"objfun_of_{self._lpm.name}",
            results=lpm_results,
        )

    def _require_objective(self) -> pd.DataFrame:
        if self._objective is None:
            raise RuntimeError("objective_function_build() must be called first")
        return self._objective

    def concentrations_frame(self) -> pd.DataFrame:
        """Return a defensive copy of sampled concentrations."""
        return self._require_concentrations().copy()

    def objective_function_frame(self) -> pd.DataFrame:
        """Return a defensive copy of sampled objective values."""
        return self._require_objective().copy()

    def parameter_names(self) -> list[str]:
        """Return the ordered parameter names of the sampled LPM."""
        return list(self._grid.names)

    def analysis_reach_conc(self) -> None:
        """Compute and optionally plot reachable concentrations."""
        self.compute_concentrations()
        if self.display_reachable:
            self.display_concentrations_with_data()

    def analysis_calibration(self, lpm_results=None) -> None:
        """Compute the configured reachable and objective analyses."""
        self.compute_concentrations()
        if self.display_reachable:
            self.display_concentrations_with_data()
        if self.display_objective:
            self.objective_function_build()
            self.objective_function_display(lpm_results)


__all__ = ["SystematicSampling"]
