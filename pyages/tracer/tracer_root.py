# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Core tracer data model and I/O utilities.

Loads tracer recharge chronologies from local datasets, provides
interpolation and accessors for concentration values, and exposes
helper methods used by convolution and calibration modules. This
module is the entry point for tracer-specific metadata and data
normalization.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import interpolate

from pyages._plotting import create_figure, finalize_figure
from pyages.config.runtime import DisplayOptions
from pyages.tracer.config import load_tracer_config
from pyages.tracer.errors import TracerConfigError, TracerDataError


class Tracer:
    """
    Chemical tracer for groundwater age dating.

    Represents a chemical element (atom, isotope, or molecule) used as a tracer
    in hydrogeological studies. Manages atmospheric recharge chronicles,
    radioactive decay, and geoproduction for groundwater age dating applications.

    Attributes
    ----------
    name : str
        Tracer identifier (e.g., 'cfc11', 'kr85', '3H')
    unit : str
        Concentration units (e.g., 'pptv', 'TU', 'pmC')
    datemin : float
        Minimum valid date for concentration computation
    datemax : float
        Maximum valid date for concentration computation

    Examples
    --------
        >>> from pathlib import Path
        >>> tracer_dir = Path("data_core/data_tracer")
        >>> tracer = Tracer(tracer_dir, name="cfc11")
        >>> print(tracer.name, tracer.unit)
        cfc11 pptv
        >>> concentration = tracer.get_concentration(date=2010.0, time=20.0)

    Notes
    -----
        Configuration is loaded from YAML format: {data_tracer}/{name}/{name}.yaml
        Optional recharge chronicle from {data_tracer}/{name}/recharge.csv

    """

    def __init__(self, dir_tracer: Path | str, name: str = "") -> None:
        """
        Tracer Class Constructor from an ensemble of external files.

        Parameters
        ----------
        dir_tracer : Path or str
            Root directory where the tracers are stored.
            High-level callers normally use
            `pyages.config.paths.DIRECTORY_TRACER_DATA`.
        name : str
            Tracer name (e.g., 'cfc11', 'kr85', '3H')

        Raises
        ------
        TracerDataError
            If configuration files cannot be read
        TracerConfigError
            If configuration is invalid or incomplete
        """
        root = Path(dir_tracer)
        config = load_tracer_config(root / name / f"{name}.yaml", name)

        self.__name = name
        self.__unit = config.unit
        self.__recharge_constant = config.recharge_constant or 0.0
        self.__has_constant_recharge = config.recharge_constant is not None
        self.__has_chronicle = config.has_chronicle
        self.__geoproduction_enabled = config.production_rate is not None
        self.__geoproduction_rate = config.production_rate or 0.0
        self.__decay_enabled = config.decay_rate is not None
        self.__decay_rate = config.decay_rate
        self.datemin = config.datemin
        self.datemax = config.datemax
        self.__recharge_chronicle_file = None
        self.__recharge_chronicle_interp = None

        # Load recharge chronicle if specified
        if self.__has_chronicle:
            recharge_file = root / name / "recharge.csv"
            try:
                # Read CSV, skipping comment lines starting with #
                self.__recharge_chronicle_file = pd.read_csv(recharge_file, comment="#")
            except FileNotFoundError as exc:
                raise TracerDataError(
                    f"Recharge chronicle CSV file not found: {recharge_file}\n"
                    f"Please create a recharge.csv file for tracer '{name}'"
                ) from exc
            except Exception as e:
                raise TracerDataError(
                    f"Error reading recharge chronicle {recharge_file}: {e}"
                ) from e

            # Create interpolation function for the input chronicle
            self.__recharge_chronicle_interp = interpolate.interp1d(
                self.__recharge_chronicle_file.iloc[:, 0],
                self.__recharge_chronicle_file.iloc[:, 1],
                kind="linear",
            )

            # Update date range from chronicle
            self.datemin = float(self.__recharge_chronicle_file.iloc[:, 0].min())
            self.datemax = float(self.__recharge_chronicle_file.iloc[:, 0].max())

        # Validate that required data are provided
        if self.datemin is None:
            raise TracerConfigError(
                f"Tracer {name}: datemin not defined in configuration"
            )
        if self.datemax is None:
            raise TracerConfigError(
                f"Tracer {name}: datemax not defined in configuration"
            )
        if self.datemin >= self.datemax:
            raise TracerConfigError(
                f"Tracer {name}: datemin ({self.datemin}) must be less than datemax ({self.datemax})"
            )

    @property
    def unit(self) -> str:
        """Unit of tracer concentration (e.g., 'pptv', 'TU', 'pmC')."""
        return self.__unit

    @property
    def name(self) -> str:
        """Tracer name (e.g., 'cfc11', 'kr85', '3H')."""
        return self.__name

    def __check_date_range(self, date: float | npt.NDArray[np.float64]) -> bool:
        """
        Checks that date is in admissible range, whether it is a scalar or an array.

        Parameters
        ----------
        date : float or ndarray
            Single date or array of dates to check

        Returns
        -------
        bool
            True if all dates are within [datemin, datemax], False otherwise
        """
        if isinstance(date, np.ndarray):
            return not (any(date > self.datemax) or any(date < self.datemin))
        else:
            return (date <= self.datemax) and (date >= self.datemin)

    def get_concentration(
        self,
        date: float | npt.NDArray[np.float64],
        time: float | npt.NDArray[np.float64],
    ) -> float | npt.NDArray[np.float64]:
        """
        Computes concentrations of tracers.

        Parameters
        ----------
        date : float or ndarray
            Date(s) at which concentrations are computed.
            date - time = date of recharge for the input chronicle
        time : float or ndarray
            Time(s) at which concentrations are computed.
            Time necessary for decay and geoproduction

        Returns
        -------
        float or ndarray
            Concentrations at the given date and time. Returns float if inputs
            are scalars, ndarray if inputs are arrays.
        """
        c = 0

        # Compute recharge component
        if self.__has_chronicle or self.__has_constant_recharge:
            if self.__has_chronicle:
                if self.__check_date_range(date):
                    # Recharge concentrations obtained by interpolation
                    c1 = self.__recharge_chronicle_interp(date)
                else:
                    # Handle dates outside valid range
                    if isinstance(date, np.ndarray):
                        # Vectorized approach instead of loop
                        valid_mask = (date >= self.datemin) & (date <= self.datemax)
                        c1 = np.zeros_like(date, dtype=float)
                        if valid_mask.any():
                            c1[valid_mask] = self.__recharge_chronicle_interp(
                                date[valid_mask]
                            )
                    else:
                        c1 = 0

            elif self.__has_constant_recharge:
                # Constant recharge concentrations, creates vector of the required size
                c1 = self.__recharge_constant * np.ones_like(time)

            # Apply decay to recharge component
            if self.__decay_enabled:
                c1 = c1 * np.exp(-self.__decay_rate * time)

            c = c + c1

        # Compute geoproduction component
        if self.__geoproduction_enabled:
            if self.__decay_enabled:
                c2 = (
                    self.__geoproduction_rate
                    * (1 - np.exp(-self.__decay_rate * time))
                    / self.__decay_rate
                )
            else:
                c2 = self.__geoproduction_rate * time
            c = c + c2

        return c

    def mean_value(self, date: float) -> float:
        """
        Mean value of chronicle taken at date "date".

        Parameters
        ----------
        date : float
            Reference date for computing the mean

        Returns
        -------
        float
            Mean concentration value over the chronicle period
        """
        # Sampling dates
        t = self.datemin + (date - self.datemin) * np.arange(0, 1, 1 / 1000)
        # Computes convolution
        return float(np.mean(self.get_concentration(t, date - t)))

    def max_value(self) -> float:
        """
        Max value of recharge chronicle concentrations.

        Returns
        -------
        float
            Maximum concentration value

        Raises
        ------
        ValueError
            If tracer has no recharge chronicle
        """
        if not self.__has_chronicle:
            raise ValueError(
                f"Tracer {self.__name} has no recharge chronicle. "
                "max_value() only works with chronicle-based tracers."
            )
        return float(self.__recharge_chronicle_file.iloc[:, 1].max())

    @property
    def convolution_dates(self) -> npt.NDArray[np.float64] | None:
        """Return recharge chronicle dates used as convolution grid knots."""
        if self.__recharge_chronicle_file is None:
            return None
        return self.__recharge_chronicle_file.iloc[:, 0].to_numpy(dtype=float)

    @property
    def convolution_initial_bins(self) -> int:
        """Return the initial grid size used when no chronicle is available."""
        return 64

    def display(self, display_options: DisplayOptions) -> None:
        """
        Display chemical element with plots.

        Parameters
        ----------
        display_options : DisplayOptions
            Display configuration options
        """
        if display_options.text:
            print("chemical:", self.__name)

        if not display_options.figure:
            return

        # Plotting the input chronicle
        if self.__has_chronicle:
            recharge_figure, recharge_axis = plt.subplots(figsize=(6, 4))
            self.__recharge_chronicle_file.plot(
                x=self.__recharge_chronicle_file.columns[0],
                y=self.__recharge_chronicle_file.columns[1],
                title="input chronicle (recharge) for " + self.__name,
                ax=recharge_axis,
            )
            finalize_figure(
                recharge_figure,
                display_options.figure_path(self.__name + "_recharge"),
                close=display_options.figure_close,
            )

        # extracting the data
        date = np.linspace(self.datemin, self.datemax, 1000)
        time = self.datemax - date
        c = self.get_concentration(date, time)

        figure, axis = create_figure(
            x_label="date",
            y_label="concentrations",
            title=self.__name,
        )

        # plot of the data
        axis.plot(date, c, "r", label=self.__name)

        finalize_figure(
            figure,
            display_options.figure_path(self.__name + "_chronicle"),
            close=display_options.figure_close,
        )
