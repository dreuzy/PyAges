"""Prepared scientific problem shared by calibration methods."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from pyage.calibration.utils.objective_functions import L2_norm_diff
from pyage.calibration.utils.systematic_sampling import SystematicSampling
from pyage.config.paths import DIRECTORY_LPM_DATA
from pyage.config.runtime import DisplayOptions
from pyage.convolution.convolution_tracers import ConvolutionTracers
from pyage.lpm.lpm_build import lpm_build

if TYPE_CHECKING:
    from pyage.concentrations.concentrations import Concentrations
    from pyage.lpm.core.lpm_base import LpmBase


class CalibrationProblem:
    """Observations, LPM and tracers required by a calibration.

    A problem is prepared once, then passed to a calibration method such as
    :class:`Simplex` or :class:`MetropolisHastings`. Systematic exploration is
    available through :attr:`sampling` but is not a parent class of the
    problem.
    """

    def __init__(
        self,
        observations: Concentrations,
        lpm_type: str,
        *,
        display_options: DisplayOptions | None = None,
        lpm_directory: str | Path = DIRECTORY_LPM_DATA,
        tracer_data_directory: str | Path | None = None,
        sample_count: int = 1000,
        explore_objective: bool = True,
        explore_reachable: bool = True,
    ) -> None:
        self.observations = observations
        self.lpm_type = lpm_type
        self.lpm_directory = Path(lpm_directory)
        self.tracer_data_directory = (
            Path(tracer_data_directory) if tracer_data_directory is not None else None
        )
        self.sample_count = sample_count
        self.explore_objective = explore_objective
        self.explore_reachable = explore_reachable
        self.display_options = display_options or DisplayOptions()

        self.lpm: LpmBase | None = None
        self.tracers: ConvolutionTracers | None = None
        self._sampling: SystematicSampling | None = None

    def prepare(self) -> CalibrationProblem:
        """Initialize and return this problem for fluent construction."""
        self.initialize()
        return self

    @property
    def is_prepared(self) -> bool:
        """Whether the LPM, tracers and exploration helper are ready."""
        return (
            self.lpm is not None
            and self.tracers is not None
            and self._sampling is not None
        )

    @property
    def sampling(self) -> SystematicSampling:
        """Return the systematic exploration associated with this problem."""
        self.ensure_prepared()
        assert self._sampling is not None
        return self._sampling

    def initialize(self) -> None:
        """Build the LPM, tracer collection and systematic exploration."""
        self.lpm = lpm_build(self.lpm_type, self.lpm_directory)
        self.tracers = ConvolutionTracers(
            names=self.observations.cv.iloc[:, 0],
            date=self.observations.cv["date"],
            tracer_data_dir=self.tracer_data_directory,
        )
        self.observations.error_affect_from_mean(
            self.tracers.mean_value(self.observations.cv["date"].mean())
        )
        self.tracers.prepare(self.lpm)
        self._sampling = SystematicSampling(
            self.lpm_type,
            self.observations.names(),
            date=self.observations.cv["date"],
            cdata=self.observations,
            nmodels=self.sample_count,
            objfunc=self.explore_objective,
            reachconc=self.explore_reachable,
            display_options=self.display_options,
            directory_lpm=self.lpm_directory,
            tracer_data_dir=self.tracer_data_directory,
        )

    def ensure_prepared(self) -> None:
        """Raise a clear error when the problem has not been initialized."""
        if not self.is_prepared:
            raise RuntimeError(
                "CalibrationProblem.initialize() must be called before calibration."
            )

    def objective_function(
        self,
        parameters,
        observed_values,
        observed_errors,
        *,
        return_concentrations: bool = False,
    ):
        """Evaluate the normalized squared residual for one parameter vector."""
        self.ensure_prepared()
        errors = np.asarray(observed_errors, dtype=float)
        if np.any(errors <= 0.0) or not np.all(np.isfinite(errors)):
            raise ValueError("Calibration errors must be finite and strictly positive.")
        assert self.lpm is not None
        assert self.tracers is not None
        self.lpm.set_param_from_array(parameters)
        modeled = self.tracers.convolve(self.lpm, apply_age_correction=True)
        objective = float(sum(L2_norm_diff(observed_values, modeled, errors)))
        if return_concentrations:
            return objective, modeled
        return objective

    def analyze(self, results=None) -> None:
        """Run the optional systematic reachable/objective analysis."""
        self.sampling.analysis_calibration(results)


__all__ = ["CalibrationProblem"]
