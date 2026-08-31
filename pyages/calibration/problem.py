# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Scientific state and objective shared by calibration methods.

``CalibrationProblem`` is the boundary between input preparation and search
algorithms.  It constructs one LPM and one ordered collection of tracer
convolutions, validates observation units, resolves missing uncertainties, and
then exposes a single chi-square objective.  Optimizers and samplers therefore
operate on the same prepared forward model instead of rebuilding scientific
objects independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from pyages.calibration import target_signature as target_signatures
from pyages.calibration.exploration.systematic import SystematicSampling
from pyages.calibration.objective import squared_normalized_residuals
from pyages.config.paths import DIRECTORY_LPM_DATA
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm.factory import build_lpm

if TYPE_CHECKING:
    from pyages.concentrations import Concentrations
    from pyages.lpm.core.lpm_base import LpmBase


def resolve_observation_errors(
    observations: Concentrations,
    *,
    tracer_data_directory: str | Path | None = None,
    missing_error_relative_fraction: float = 0.01,
) -> ConvolutionTracers:
    """Validate units and resolve zero observation errors from tracer means.

    This is the shared scientific input boundary used by calibration and by
    workflows that must persist or analyse the exact effective uncertainties
    before constructing a :class:`CalibrationProblem`.
    """
    tracers = ConvolutionTracers(
        names=observations.observation_tracer_names(),
        date=observations.frame["date"],
        tracer_data_dir=tracer_data_directory,
    )
    tracers.validate_observation_units(observations)
    observations.fill_missing_errors_from_means(
        tracers.mean_values_at_sampling_dates(),
        fraction=missing_error_relative_fraction,
    )
    errors = observations.frame["error"].to_numpy(dtype=float)
    if np.any(errors <= 0.0) or not np.all(np.isfinite(errors)):
        raise ValueError(
            "Observation errors must be finite and strictly positive after "
            "resolving missing values"
        )
    return tracers


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
        missing_error_relative_fraction: float = 0.01,
        sample_count: int = 1000,
        explore_objective: bool = True,
        explore_reachable: bool = True,
    ) -> None:
        """Store calibration inputs without preparing scientific objects yet.

        Construction is deliberately cheap.  Call :meth:`prepare` or
        :meth:`initialize` before passing the problem to a calibration method.
        Systematic parameter-space exploration is allocated lazily through
        :attr:`sampling` because ordinary calibrations do not need its grid.
        """
        self.observations = observations
        self.lpm_type = lpm_type
        self.lpm_directory = Path(lpm_directory)
        self.tracer_data_directory = (
            Path(tracer_data_directory) if tracer_data_directory is not None else None
        )
        self.missing_error_relative_fraction = missing_error_relative_fraction
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
        """Whether the scientific model and tracer convolutions are ready."""
        return self.lpm is not None and self.tracers is not None

    @property
    def sampling(self) -> SystematicSampling:
        """Create and return this problem's optional systematic exploration."""
        self.ensure_prepared()
        if self._sampling is None:
            self._sampling = self._build_sampling()
        return self._sampling

    def _build_sampling(self) -> SystematicSampling:
        """Build systematic exploration only when a caller requests it."""
        return SystematicSampling(
            self.lpm_type,
            self.observations.observation_tracer_names(),
            date=self.observations.frame["date"],
            observations=self.observations,
            sample_count=self.sample_count,
            explore_objective=self.explore_objective,
            explore_reachable=self.explore_reachable,
            display_options=self.display_options,
            lpm_directory=self.lpm_directory,
            tracer_data_directory=self.tracer_data_directory,
        )

    def initialize(self) -> None:
        """Build and cross-check the forward model required by calibration.

        The order of these operations is part of the scientific contract:
        units are checked before missing errors are inferred, and tracer
        convolutions are prepared only after the observation boundary is
        valid.  Reinitialization replaces any cached systematic exploration.
        """
        # Model parameters and bounds come from the selected LPM definition.
        self.lpm = build_lpm(self.lpm_type, self.lpm_directory)
        # Preserve observation row order and resolve zero uncertainty
        # placeholders once, never inside an optimizer or MCMC transition.
        self.tracers = resolve_observation_errors(
            self.observations,
            tracer_data_directory=self.tracer_data_directory,
            missing_error_relative_fraction=self.missing_error_relative_fraction,
        )
        self.tracers.prepare(self.lpm)
        self._sampling = None

    def ensure_prepared(self) -> None:
        """Raise a clear error when the problem has not been initialized."""
        if not self.is_prepared:
            raise RuntimeError(
                "CalibrationProblem.initialize() must be called before calibration."
            )

    def target_signature(self) -> target_signatures.CalibrationTargetSignature:
        """Return the immutable scientific identity of this prepared problem.

        The signature is recalculated from the resolved model, effective
        ordered observations, and prepared tracer grids. Consequently callers
        can compare independently constructed problems immediately before a
        numerical method starts, while reporting-only state such as display
        directories cannot create a false mismatch.
        """
        self.ensure_prepared()
        assert self.lpm is not None
        assert self.tracers is not None
        return target_signatures.build_calibration_target_signature(
            self.lpm,
            self.observations,
            self.tracers,
        )

    def objective_function(
        self,
        parameters,
        observed_values,
        observed_errors,
        *,
        return_concentrations: bool = False,
    ):
        r"""Evaluate chi-square for one LPM parameter vector.

        For ordered observations :math:`y_i`, forward predictions
        :math:`m_i(\theta)`, and finite positive one-sigma errors
        :math:`\sigma_i`, this returns

        .. math::

           \chi^2(\theta)=\sum_i
           \left[\frac{m_i(\theta)-y_i}{\sigma_i}\right]^2.

        Errors are assumed independent and Gaussian. Parameter bounds and
        priors are handled by calibration methods, not here. The modeled values
        are always produced by the physical forward model; optimizer-specific
        penalties are not hidden in concentrations.

        Parameters
        ----------
        parameters : array-like
            LPM parameters in ``lpm.get_param_names()`` order and native units.
        observed_values, observed_errors : array-like
            Concentrations and one-sigma uncertainties in matching tracer order
            and units.
        return_concentrations : bool
            Also return modeled concentrations when true.

        Returns
        -------
        float or tuple
            Dimensionless chi-square, optionally paired with modeled
            concentrations.

        Notes
        -----
        Persisted result tables retain the schema field ``obj_function`` for
        :math:`\sqrt{\chi^2/n}`. Systematic maps use the explicit field
        ``half_log_chi_square`` for :math:`0.5\log(\chi^2)`.
        """
        self.ensure_prepared()
        errors = np.asarray(observed_errors, dtype=float)
        if np.any(errors <= 0.0) or not np.all(np.isfinite(errors)):
            raise ValueError("Calibration errors must be finite and strictly positive.")
        assert self.lpm is not None
        assert self.tracers is not None
        # Objective evaluation is intentionally stateful at this low-level
        # boundary: the prepared LPM is updated, then every ordered tracer uses
        # that same parameter vector for its forward calculation.
        self.lpm.set_param_from_array(parameters)
        modeled = self.tracers.convolve(self.lpm)
        objective = float(
            np.sum(squared_normalized_residuals(observed_values, modeled, errors))
        )
        if return_concentrations:
            return objective, modeled
        return objective

    def analyze(self, results=None) -> None:
        """Run the optional systematic reachable/objective analysis."""
        self.sampling.analysis_calibration(results)


__all__ = [
    "CalibrationProblem",
    "resolve_observation_errors",
]
