# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file coordinates the forward model for one tracer, observation date, and
# water-age distribution. It selects continuous, point-mass, or mixed arithmetic
# and returns predicted concentrations, treating ages beyond the tracer history
# as zero contribution instead of redistributing their probability.

"""Orchestrate one tracer/LPM convolution across all strategy types.

This module owns date validation, finite-window semantics, cached-grid lifetime,
and strategy dispatch. Tracer-grid construction and continuous integration live
in focused helper modules; point-mass strategies use direct tracer evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pyages.config.runtime import subdivide_interval
from pyages.convolution.continuous_integration import (
    ConvolutionDiagnostics,
    convolve_prepared_grid,
    window_mass_from_provider,
)
from pyages.convolution.errors import ConvolutionError
from pyages.convolution.settings import (
    DEFAULT_CONVOLUTION_SETTINGS,
    ConvolutionSettings,
)
from pyages.convolution.tracer_grid import (
    PreparedTracerGrid,
    evaluate_tracer_response,
    prepare_tracer_grid,
)
from pyages.lpm.core.convolution_strategy import ConvolutionStrategy
from pyages.lpm.core.lpm_base import LpmBase
from pyages.tracer.protocols import ConvolutionTracerProtocol


class Convolution:
    r"""Convolve one tracer response with a transit-time distribution.

    At observation date :math:`t`, the forward model is

    .. math::

       C(t;\theta)=\int_{0}^{t-t_{min}} K(t,\tau)\,dF_\theta(\tau),

    where :math:`\tau` is water age in years, :math:`K` is the complete tracer
    response returned by
    ``ConvolutionTracerProtocol.get_concentration(t - tau, tau)``,
    and :math:`F_\theta` is the LPM probability measure. ``K`` includes any
    tracer-specific decay or production and retains the tracer concentration
    unit.

    The convolution algorithm is automatically selected based on the LPM's
    `convolution_strategy` attribute:
    - CONTINUOUS: Cached tracer grid with exact CDF masses and first moments
    - DIRAC: Direct chronicle lookup for single spike
    - DIRAC_DOUBLE: Weighted combination of two lookups
    - MIXED_DIRAC_CONTINUOUS: Weighted Dirac + continuous component

    The finite window ``[0, t - datemin]`` is a scientific boundary
    convention: LPM mass older than the recharge chronicle contributes zero
    and is not renormalized. Continuous LPMs use exact bin masses and partial
    first moments on a cached tracer-driven grid; Dirac masses use direct
    lookups, including both endpoints.

    Attributes
    ----------
    tracer : ConvolutionTracerProtocol
        Tracer instance providing concentration data.
    date : float
        Date (year) at which the convolution is performed.

    Examples
    --------
    >>> from pyages.convolution import Convolution
    >>> from pyages.lpm import build_lpm
    >>> from pyages.tracer.simple_tracers import ConstantTracer
    >>> tracer = ConstantTracer(concentration=1.0, datemin=1900.0)
    >>> lpm = build_lpm("exp")
    >>> conv = Convolution(tracer, date=2010.0)
    >>> result = conv.convolve(lpm)
    >>> result > 0.0
    True

    See Also
    --------
    pyages.convolution.settings.ConvolutionSettings
        Numerical controls whose non-default values should be reported.

    Notes
    -----
    Equations, boundary conventions, and validation links are consolidated in
    ``docs/scientific-methods.md``; implementation history and independent
    comparisons are in ``docs/convolution-method-evolution-report.md``.
    """

    def __init__(
        self,
        tracer: ConvolutionTracerProtocol,
        date: float = 2010,
        grid_settings: ConvolutionSettings | None = None,
    ) -> None:
        """
        Initialize Convolution with a tracer instance.

        Parameters
        ----------
        tracer : ConvolutionTracerProtocol
            Any tracer implementing the convolution tracer interface
            (Tracer, SyntheticTracer, ConstantTracer, DecayTracer, etc.).
        date : float
            Finite decimal year at which convolution will be computed. It must
            not precede the tracer's ``datemin``.
        grid_settings : ConvolutionSettings, optional
            Numerical controls for tracer-grid preparation and integration.

        Examples
        --------
        See the class example and :doc:`/user-guide/convolution` for
        complete single-tracer and batch workflows.
        """
        if not isinstance(tracer, ConvolutionTracerProtocol):
            raise TypeError(
                "tracer must implement the ConvolutionTracerProtocol contract"
            )
        self._tracer: ConvolutionTracerProtocol = tracer
        self._date = self._validated_observation_date(date)
        self._grid_settings = grid_settings or DEFAULT_CONVOLUTION_SETTINGS
        self._prepared_grid: PreparedTracerGrid | None = None
        self._last_diagnostics: ConvolutionDiagnostics | None = None

    @property
    def tracer(self) -> ConvolutionTracerProtocol:
        """Tracer instance providing concentration data."""
        return self._tracer

    @property
    def date(self) -> float:
        """Date (year) at which convolution is performed."""
        return self._date

    @date.setter
    def date(self, value: float) -> None:
        """Set the observation date and invalidate date-dependent state."""
        validated = self._validated_observation_date(value)
        if validated != self._date:
            # Both the response grid and diagnostics describe one specific
            # observation date and must never leak into the next evaluation.
            self._date = validated
            self._prepared_grid = None
            self._last_diagnostics = None

    def _validated_observation_date(self, value: float) -> float:
        """Return a finite numeric date at or after the tracer history start."""
        if isinstance(value, (bool, np.bool_, str, bytes)) or not np.isscalar(value):
            raise ValueError("observation date must be a finite numeric value")
        try:
            date = float(value)
            datemin = float(self._tracer.datemin)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "observation date and tracer.datemin must be numeric"
            ) from exc
        if not np.isfinite(date):
            raise ValueError("observation date must be finite")
        if not np.isfinite(datemin):
            raise ValueError("tracer.datemin must be finite")
        if date < datemin:
            raise ValueError(
                f"observation date={date} must be >= tracer.datemin={datemin}"
            )
        return date

    def _window_upper_age(self) -> float:
        """Return the validated upper age of the available tracer window."""
        try:
            date = self._validated_observation_date(self._date)
        except ValueError as exc:
            raise ConvolutionError(f"Invalid convolution window: {exc}") from exc
        return date - float(self._tracer.datemin)

    def _dirac_age_in_window(self, time: float) -> tuple[float, bool]:
        """Validate a point-mass age and report whether it is represented."""
        try:
            age = float(time)
        except (TypeError, ValueError) as exc:
            raise ConvolutionError("Dirac age must be finite and numeric") from exc
        if not np.isfinite(age):
            raise ConvolutionError("Dirac age must be finite")
        return age, 0.0 <= age <= self._window_upper_age()

    @staticmethod
    def _mixture_rate(lpm: LpmBase) -> float:
        """Return a finite mixture weight in the closed unit interval."""
        try:
            rate = float(lpm.p["rate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConvolutionError(
                f"LPM '{lpm.name}' must provide a numeric 'rate' parameter"
            ) from exc
        if not np.isfinite(rate) or not 0.0 <= rate <= 1.0:
            raise ConvolutionError(
                f"LPM '{lpm.name}' rate must be finite and in [0, 1]"
            )
        return rate

    @staticmethod
    def _require_moment_provider(
        lpm: LpmBase,
        provider,
        distribution_name: str,
    ):
        """Return a concrete vectorized CDF/partial-moment provider.

        Merely inheriting :class:`LpmBase`'s placeholder is not sufficient for
        continuous convolution; the distribution must override the method.
        """
        if provider is None:
            provider = getattr(lpm, "cdf_and_partial_first_moment", None)
        inherited_stub = (
            getattr(provider, "__func__", None) is LpmBase.cdf_and_partial_first_moment
        )
        if not callable(provider) or inherited_stub:
            raise ConvolutionError(
                f"Continuous LPM '{distribution_name}' must implement "
                "cdf_and_partial_first_moment()"
            )
        return provider

    # -------------------------------------------------------------------------
    # CDF/partial-moment convolution (tracer-driven cached grid)
    # -------------------------------------------------------------------------

    def _prepare_tracer_grid(self) -> PreparedTracerGrid:
        """Build and cache the tracer-only adaptive grid.

        Because no LPM state enters grid construction, the result is reusable
        across parameter proposals and even across different continuous LPMs.
        """
        grid = prepare_tracer_grid(
            self._tracer,
            self._date,
            self._window_upper_age(),
            settings=self._grid_settings,
        )
        self._prepared_grid = grid
        return grid

    def _convolve_continuous(
        self,
        lpm: LpmBase,
        *,
        cdf_moment_provider=None,
        distribution_name: str | None = None,
    ) -> float:
        """Convolve a continuous law using exact bin masses and first moments.

        The prepared tracer grid is rebuilt only when absent or stale. The LPM
        provider is evaluated afterward, keeping tracer preparation outside hot
        calibration loops whenever callers reuse this instance.
        """
        grid = self._prepared_grid
        if grid is None or grid.date != self._date:
            grid = self._prepare_tracer_grid()
        distribution_name = distribution_name or lpm.name
        cdf_moment_provider = self._require_moment_provider(
            lpm,
            cdf_moment_provider,
            distribution_name,
        )
        if grid.edges.size == 1:
            # ``date == datemin`` leaves a valid but empty age window.
            self._last_diagnostics = ConvolutionDiagnostics(0.0, 0, 0.0, 0)
            return 0.0
        result, diagnostics = convolve_prepared_grid(
            grid,
            cdf_moment_provider,
            distribution_name,
            self._grid_settings,
        )
        self._last_diagnostics = diagnostics
        return result

    def window_mass(self, lpm: LpmBase) -> float:
        """Return probability mass in the closed available-age window.

        The window is ``[0, date - datemin]`` years. Mass outside this window
        is excluded from :meth:`convolve` and is not renormalized, so values
        below one quantify truncation by the available tracer chronicle.

        Continuous strategies use the same provider validation as
        :meth:`convolve`, but do not need to prepare or evaluate a tracer grid.
        """
        tmax = self._window_upper_age()
        strategy = lpm.convolution_strategy
        if strategy == ConvolutionStrategy.DIRAC:
            _, represented = self._dirac_age_in_window(lpm.get_dirac_time())
            return float(represented)
        if strategy == ConvolutionStrategy.DIRAC_DOUBLE:
            first, second = lpm.get_dirac_double_time()
            rate = self._mixture_rate(lpm)
            _, first_represented = self._dirac_age_in_window(first)
            _, second_represented = self._dirac_age_in_window(second)
            return rate * float(first_represented) + (1.0 - rate) * float(
                second_represented
            )
        if strategy == ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS:
            rate = self._mixture_rate(lpm)
            _, represented = self._dirac_age_in_window(lpm.get_dirac_time())
            provider = self._require_moment_provider(
                lpm,
                getattr(lpm, "continuous_cdf_and_partial_first_moment", None),
                f"{lpm.name} continuous component",
            )
            continuous_mass = window_mass_from_provider(
                provider,
                tmax,
                f"{lpm.name} continuous component",
                self._grid_settings,
            )
            return rate * float(represented) + (1.0 - rate) * continuous_mass
        if strategy != ConvolutionStrategy.CONTINUOUS:
            raise ConvolutionError(
                f"Unsupported convolution strategy {strategy!r} for LPM '{lpm.name}'"
            )
        provider = self._require_moment_provider(lpm, None, lpm.name)
        return window_mass_from_provider(
            provider,
            tmax,
            lpm.name,
            self._grid_settings,
        )

    @property
    def diagnostics(self) -> ConvolutionDiagnostics | None:
        """Return diagnostics from the latest continuous or mixed convolution."""
        return self._last_diagnostics

    @property
    def prepared_grid(self) -> PreparedTracerGrid | None:
        """Return the cached tracer grid, if one has been prepared."""
        return self._prepared_grid

    @property
    def grid_settings(self) -> ConvolutionSettings:
        """Return the immutable tracer-grid settings used by this instance."""
        return self._grid_settings

    # -------------------------------------------------------------------------
    # Dirac convolution (direct lookup)
    # -------------------------------------------------------------------------

    def _convolution_dirac(self, lpm: LpmBase) -> float:
        """Evaluate a single Dirac mass by direct tracer lookup.

        Parameters
        ----------
        lpm : LPM
            Dirac-type LPM with get_dirac_time() method.

        Returns
        -------
        float
            Convolution result (tracer concentration).
        """
        return self._dirac_concentration(lpm.get_dirac_time())

    def _dirac_concentration(self, time: float) -> float:
        """Return a point-mass contribution only inside the tracer window."""
        age, represented = self._dirac_age_in_window(time)
        if not represented:
            return 0.0
        return float(
            evaluate_tracer_response(
                self._tracer,
                self._date,
                np.array([age]),
            )[0]
        )

    def _convolution_dirac_double(self, lpm: LpmBase) -> float:
        """Evaluate and mix two independently windowed Dirac masses.

        Parameters
        ----------
        lpm : LPM
            Double-Dirac LPM with get_dirac_double_time() and 'rate' parameter.

        Returns
        -------
        float
            Weighted sum of two Dirac lookups.
        """
        rate = self._mixture_rate(lpm)
        [time1, time2] = lpm.get_dirac_double_time()
        convol1 = self._dirac_concentration(time1)
        convol2 = self._dirac_concentration(time2)
        return rate * convol1 + (1.0 - rate) * convol2

    # -------------------------------------------------------------------------
    # Mixed convolution (Dirac + normalized continuous component)
    # -------------------------------------------------------------------------

    def _convolve_mixed_dirac_continuous(self, lpm: LpmBase) -> float:
        """Combine normalized Dirac and continuous component convolutions.

        Parameters
        ----------
        lpm : LPM
            Mixed LPM whose ``rate`` weights the Dirac component.

        Returns
        -------
        float
            Weighted sum of Dirac and exponential convolution.
        """
        rate = self._mixture_rate(lpm)
        dirac_part = self._convolution_dirac(lpm)
        # The model PDF represents the weighted continuous part of the full
        # mixture.  Integrate its normalized component here, then apply the
        # mixture weight exactly once below.
        continuous_part = self._convolve_continuous(
            lpm,
            cdf_moment_provider=lpm.continuous_cdf_and_partial_first_moment,
            distribution_name=f"{lpm.name} continuous component",
        )
        continuous_diagnostics = self._last_diagnostics
        if continuous_diagnostics is None:
            raise ConvolutionError("Continuous mixture diagnostics are missing")
        _, represented = self._dirac_age_in_window(lpm.get_dirac_time())
        dirac_mass = float(represented)
        # Diagnostics must describe the full mixture, not just the continuous
        # helper call that populated ``_last_diagnostics`` above.
        self._last_diagnostics = ConvolutionDiagnostics(
            window_mass=(
                rate * dirac_mass + (1.0 - rate) * continuous_diagnostics.window_mass
            ),
            n_bins=continuous_diagnostics.n_bins,
            min_weight=(1.0 - rate) * continuous_diagnostics.min_weight,
            clipped_weight_count=continuous_diagnostics.clipped_weight_count,
        )
        return rate * dirac_part + (1.0 - rate) * continuous_part

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def prepare(self) -> PreparedTracerGrid:
        """Eagerly build and return the tracer-response grid."""
        return self._prepare_tracer_grid()

    def _convolve_once(self, lpm: LpmBase) -> float:
        """Dispatch exactly one algorithm from the LPM's declared strategy."""
        self._last_diagnostics = None
        strategy = lpm.convolution_strategy

        if strategy == ConvolutionStrategy.CONTINUOUS:
            return self._convolve_continuous(lpm)
        if strategy == ConvolutionStrategy.DIRAC:
            return self._convolution_dirac(lpm)
        if strategy == ConvolutionStrategy.DIRAC_DOUBLE:
            return self._convolution_dirac_double(lpm)
        if strategy == ConvolutionStrategy.MIXED_DIRAC_CONTINUOUS:
            return self._convolve_mixed_dirac_continuous(lpm)
        raise ConvolutionError(
            f"Unsupported convolution strategy {strategy!r} for LPM '{lpm.name}'"
        )

    def convolve(self, lpm: LpmBase) -> float:
        """Compute tracer concentration at the configured observation date.

        The algorithm is automatically selected based on the LPM's
        ``convolution_strategy`` attribute. The result has the tracer's
        concentration unit. Ages and dates are decimal years, and probability
        older than ``date - datemin`` contributes zero without renormalization.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model defining the transit time distribution.
        Returns
        -------
        float
            Convolution result (tracer concentration).

        """
        result = float(self._convolve_once(lpm))
        if not np.isfinite(result):
            raise ConvolutionError(
                f"Convolution of tracer '{self._tracer.name}' with LPM '{lpm.name}' "
                "returned a non-finite value"
            )
        return result

    def convolve_date_range(
        self,
        lpm: LpmBase,
        date1: float,
        date2: float,
        *,
        resolution: int = 50,
    ) -> pd.DataFrame:
        """Compute convolution over a range without changing :attr:`date`.

        Parameters
        ----------
        lpm : LPM
            Lumped Parameter Model for convolution.
        date1 : float
            Start date (year).
        date2 : float
            End date (year).
        resolution : int
            Number of equal intervals; the returned frame has one additional
            row because both endpoints are included. Booleans and non-integral
            values are rejected.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: 'date', 'concentration', 'element'.

        Raises
        ------
        ValueError
            If either date is non-finite or precedes the tracer history, or if
            ``resolution`` is not an integer greater than or equal to one.
        """
        start = self._validated_observation_date(date1)
        end = self._validated_observation_date(date2)
        try:
            dates = subdivide_interval(start, end, resolution)
        except ValueError as exc:
            raise ValueError(f"resolution must be an integer >= 1: {exc}") from exc
        original_date = self._date
        original_grid = self._prepared_grid
        original_diagnostics = self._last_diagnostics
        try:
            concentrations = []
            for sample_date in dates:
                self.date = float(sample_date)
                concentrations.append(self.convolve(lpm))
        finally:
            # Date-range evaluation is observational: restore the complete
            # cache/diagnostic state even if one intermediate date fails.
            self._date = original_date
            self._prepared_grid = original_grid
            self._last_diagnostics = original_diagnostics
        return pd.DataFrame(
            {
                "date": dates,
                "concentration": concentrations,
                "element": self._tracer.name,
            }
        )


__all__ = ["Convolution"]
