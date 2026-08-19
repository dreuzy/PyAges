# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Core tracer data model and I/O utilities.
Loads tracer recharge chronologies from local datasets, provides
interpolation and accessors for concentration values, and exposes
helper methods used by convolution and calibration modules. This
module is the entry point for tracer-specific metadata and data
normalization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import yaml
from scipy import interpolate

from pyage.config.paths import DIRECTORY_TRACER_DATA
from pyage.config.runtime import DisplayOptions
from pyage.tracer.decay import rate_from_config


# Custom Exceptions
class TracerConfigError(Exception):
    """Raised when tracer configuration is invalid or incomplete."""

    pass


class TracerDataError(Exception):
    """Raised when tracer data files are missing or cannot be read."""

    pass


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

    def __init__(self, dir_tracer: Union[Path, str], name: str = "") -> None:
        """
        Tracer Class Constructor from an ensemble of external files.

        Parameters
        ----------
        dir_tracer : Path or str
            Root directory where the tracers are stored.
            High-level callers normally use
            `pyage.config.paths.DIRECTORY_TRACER_DATA`.
        name : str
            Tracer name (e.g., 'cfc11', 'kr85', '3H')

        Raises
        ------
        TracerDataError
            If configuration files cannot be read
        TracerConfigError
            If configuration is invalid or incomplete
        """
        # Initialize all attributes with default values
        self.__name = name
        self.__unit = "unknown"
        self.__recharge_constant = 0.0
        self.__has_constant_recharge = False
        self.__has_chronicle = False
        self.__geoproduction_enabled = False
        self.__geoproduction_rate = 0.0
        self.__decay_enabled = False
        self.__decay_rate = None
        self.datemin = None
        self.datemax = None
        self.__recharge_chronicle_file = None
        self.__recharge_chronicle_interp = None

        # Load configuration file (YAML format).
        self._load_config(Path(dir_tracer), name)

        # Load recharge chronicle if specified
        if self.__has_chronicle:
            recharge_file = dir_tracer / name / "recharge.csv"
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

    def _load_config(self, dir_tracer: Path, name: str) -> None:
        """
        Load configuration file in YAML format.

        Parameters
        ----------
        dir_tracer : Path
            Root directory where tracers are stored
        name : str
            Tracer name

        Raises
        ------
        TracerDataError
            If YAML configuration file is not found
        """
        yaml_file = dir_tracer / name / f"{name}.yaml"

        if not yaml_file.exists():
            raise TracerDataError(
                f"YAML configuration file not found: {yaml_file}\n"
                f"Please create a .yaml configuration file for tracer '{name}'"
            )

        self._load_yaml_config(yaml_file, name)

    def _load_yaml_config(self, config_file: Path, name: str) -> None:
        """
        Load configuration from YAML file.

        Parameters
        ----------
        config_file : Path
            Path to YAML configuration file
        name : str
            Tracer name for error messages

        Raises
        ------
        TracerDataError
            If YAML file cannot be read
        TracerConfigError
            If YAML structure is invalid
        """
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError as exc:
            raise TracerDataError(
                f"YAML configuration file not found: {config_file}"
            ) from exc
        except yaml.YAMLError as e:
            raise TracerDataError(
                f"Error parsing YAML configuration {config_file}: {e}"
            ) from e
        except Exception as e:
            raise TracerDataError(
                f"Error reading YAML configuration {config_file}: {e}"
            ) from e

        if not isinstance(config, dict):
            raise TracerConfigError(
                f"YAML configuration must be a dictionary, got {type(config).__name__}"
            )

        try:
            self.__decay_rate = rate_from_config(config)
            self.__decay_enabled = self.__decay_rate is not None
        except ValueError as exc:
            raise TracerConfigError(f"Tracer {name}: {exc}") from exc

        # Parse each configuration parameter
        for param_name, value in config.items():
            if param_name == "recharge_constant":
                self.__recharge_constant = float(value)
                self.__has_constant_recharge = True
            elif param_name == "recharge":
                self.__has_chronicle = bool(value)
            elif param_name == "production_rate":
                self.__geoproduction_enabled = True
                self.__geoproduction_rate = float(value)
                if self.__geoproduction_rate < 0:
                    raise TracerConfigError(
                        f"Tracer {name}: Geoproduction rate must be non-negative, "
                        f"got {self.__geoproduction_rate}"
                    )
            elif param_name in {"half_life", "decay_mean_lifetime"}:
                continue
            elif param_name == "unit":
                self.__unit = str(value)
            elif param_name == "datemin":
                self.datemin = float(value)
            elif param_name == "datemax":
                self.datemax = float(value)
            elif isinstance(value, (dict, list)):
                # Allow example/site metadata blocks while keeping strict
                # validation on the core scalar configuration keys.
                continue
            else:
                raise TracerConfigError(
                    f"Unknown parameter in {name}.yaml: '{param_name}'"
                )

    @property
    def unit(self) -> str:
        """Unit of tracer concentration (e.g., 'pptv', 'TU', 'pmC')."""
        return self.__unit

    @property
    def name(self) -> str:
        """Tracer name (e.g., 'cfc11', 'kr85', '3H')."""
        return self.__name

    def __check_date_range(self, date: Union[float, npt.NDArray[np.float64]]) -> bool:
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
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]],
    ) -> Union[float, npt.NDArray[np.float64]]:
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

        # Plotting the input chronicle
        if self.__has_chronicle:
            plt.figure()  # Create new figure for recharge chronicle
            self.__recharge_chronicle_file.plot(
                x=self.__recharge_chronicle_file.columns[0],
                y=self.__recharge_chronicle_file.columns[1],
                title="input chronicle (recharge) for " + self.__name,
            )
            display_options.figure_close_fx(self.__name + "_recharge")

        # extracting the data
        date = np.linspace(self.datemin, self.datemax, 1000)
        time = self.datemax - date
        c = self.get_concentration(date, time)

        # Create new figure for concentration plot
        plt.figure()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.set_xlabel("date", fontsize=16, fontweight="bold")
        ax.set_ylabel("concentrations", fontsize=14, fontweight="bold")
        ax.tick_params(axis="x", labelsize=14)
        ax.tick_params(axis="y", labelsize=14)
        ax.grid(True)
        ax.set_title(self.__name, fontsize=22, fontweight="bold")

        # plot of the data
        ax.plot(date, c, "r", label=self.__name)

        display_options.figure_close_fx(self.__name + "_chronicle")


# ------------------------------------------------------
# Main - Example usage
# ------------------------------------------------------
def main() -> None:
    """
    Main function demonstrating tracer loading and display.

    Automatically discovers and loads all available tracers.
    """
    tracer_dir = DIRECTORY_TRACER_DATA
    if not tracer_dir.exists():
        raise FileNotFoundError(f"Tracer data directory not found: {tracer_dir}")

    # Automatically discover all available tracers by listing subdirectories
    print(f"Scanning tracer directory: {tracer_dir}")
    tracer_names = sorted(
        [
            d.name
            for d in tracer_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
    )

    if not tracer_names:
        print("No tracers found in directory.")
        return

    print(f"Found {len(tracer_names)} tracers: {', '.join(tracer_names)}\n")

    # Configure display options
    display_options = DisplayOptions()
    display_options.text = True
    display_options.figure_save = False
    display_options.figure_close = False

    # Statistics
    success_count = 0
    error_count = 0

    # Load and display each tracer
    for name in tracer_names:
        print(f"\n{'=' * 50}")
        print(f"Loading tracer: {name}")
        print(f"{'=' * 50}")

        try:
            tracer = Tracer(tracer_dir, name=name)
            print(f"  Name: {tracer.name}")
            print(f"  Unit: {tracer.unit}")
            print(f"  Date range: {tracer.datemin} - {tracer.datemax}")
            tracer.display(display_options)
            success_count += 1

        except (TracerDataError, TracerConfigError) as e:
            print(f"  Error loading tracer '{name}': {e}")
            error_count += 1

    # Summary
    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print(f"{'=' * 50}")
    print(f"Successfully loaded: {success_count}/{len(tracer_names)} tracers")
    if error_count > 0:
        print(f"Errors: {error_count}")


if __name__ == "__main__":
    main()
