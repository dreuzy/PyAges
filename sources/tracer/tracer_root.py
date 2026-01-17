# -*- coding: utf-8 -*-
"""
Created on Tue Mar 23 03:23:24 2021

@author: Jean-Raynald de Dreuzy
"""

from typing import Union, Optional
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import interpolate
from pathlib import Path


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

    Attributes:
        name (str): Tracer identifier (e.g., 'cfc11', 'kr85', '3H')
        unit (str): Concentration units (e.g., 'pptv', 'TU', 'pmC')
        datemin (float): Minimum valid date for concentration computation
        datemax (float): Maximum valid date for concentration computation

    Examples:
        >>> from pathlib import Path
        >>> tracer_dir = Path("sources/tracer_data")
        >>> tracer = Tracer(tracer_dir, name="cfc11")
        >>> print(tracer.name, tracer.unit)
        cfc11 pptv
        >>> concentration = tracer.get_concentration(date=2010.0, time=20.0)

    Note:
        Configuration is loaded from {tracer_data}/{name}/{name}.txt
        Optional recharge chronicle from {tracer_data}/{name}/recharge.txt
    """
    def __init__(self, dir_tracer: Union[Path, str], name: str = "") -> None:
        """
        Tracer Class Constructor from an ensemble of external files.

        Args:
            dir_tracer: Path or str
                Root directory where the tracers are stored.
                Default defined in the file global_parameters.py
            name: str
                Tracer name (e.g., 'cfc11', 'kr85', '3H')

        Raises:
            TracerDataError: If configuration files cannot be read
            TracerConfigError: If configuration is invalid or incomplete
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
        self.__decay_time = None
        self.datemin = None
        self.datemax = None
        self.__recharge_chronicle_file = None
        self.__recharge_chronicle_interp = None

        # Load configuration file
        config_file = dir_tracer / name / f"{name}.txt"
        try:
            table = pd.read_csv(config_file, header=None)
        except FileNotFoundError:
            raise TracerDataError(
                f"Tracer configuration file not found: {config_file}"
            )
        except Exception as e:
            raise TracerDataError(
                f"Error reading tracer configuration file {config_file}: {e}"
            )

        # Parse configuration parameters using handler dispatch
        self._parse_configuration(table, name)

        # Load recharge chronicle if specified
        if self.__has_chronicle:
            recharge_file = dir_tracer / name / "recharge.txt"
            try:
                self.__recharge_chronicle_file = pd.read_table(recharge_file, header=0)
            except FileNotFoundError:
                raise TracerDataError(
                    f"Recharge chronicle file not found: {recharge_file}"
                )
            except Exception as e:
                raise TracerDataError(
                    f"Error reading recharge chronicle {recharge_file}: {e}"
                )

            # Create interpolation function for the input chronicle
            self.__recharge_chronicle_interp = interpolate.interp1d(
                self.__recharge_chronicle_file.iloc[:, 0],
                self.__recharge_chronicle_file.iloc[:, 1],
                kind="linear"
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

    def _parse_configuration(self, table: pd.DataFrame, name: str) -> None:
        """
        Parse configuration table using handler dispatch pattern.

        Args:
            table: DataFrame containing configuration parameters
            name: Tracer name for error messages
        """
        # Handler methods for each parameter type
        handlers = {
            'recharge_constant': self._handle_recharge_constant,
            'recharge': self._handle_recharge_chronicle,
            'production rate': self._handle_geoproduction,
            'decay characteristic time': self._handle_decay,
            'unit': self._handle_unit,
            'datemin': self._handle_datemin,
            'datemax': self._handle_datemax,
        }

        for i in range(len(table)):
            param_name = table.iloc[i, 0]

            if param_name not in handlers:
                raise TracerConfigError(
                    f"Unknown parameter in {name}.txt: '{param_name}'"
                )

            # Dispatch to appropriate handler
            handlers[param_name](table.iloc[i], name)

    def _handle_recharge_constant(self, row: pd.Series, name: str) -> None:
        """Handle recharge_constant parameter."""
        self.__recharge_constant = float(row[1])
        self.__has_constant_recharge = True

    def _handle_recharge_chronicle(self, row: pd.Series, name: str) -> None:
        """Handle recharge parameter (chronicle flag)."""
        self.__has_chronicle = bool(int(row[1]))

    def _handle_geoproduction(self, row: pd.Series, name: str) -> None:
        """Handle production rate parameter."""
        self.__geoproduction_enabled = True
        self.__geoproduction_rate = float(row[1])
        if self.__geoproduction_rate < 0:
            raise TracerConfigError(
                f"Tracer {name}: Geoproduction rate must be non-negative, "
                f"got {self.__geoproduction_rate}"
            )

    def _handle_decay(self, row: pd.Series, name: str) -> None:
        """Handle decay characteristic time parameter."""
        self.__decay_enabled = True
        self.__decay_time = float(row[1])
        if self.__decay_time <= 0:
            raise TracerConfigError(
                f"Tracer {name}: Decay time must be positive, got {self.__decay_time}"
            )

    def _handle_unit(self, row: pd.Series, name: str) -> None:
        """Handle unit parameter."""
        if len(row) < 3:
            raise TracerConfigError(
                f"Tracer {name}: Unit parameter requires 3 columns, found {len(row)}"
            )
        self.__unit = str(row[2])

    def _handle_datemin(self, row: pd.Series, name: str) -> None:
        """Handle datemin parameter."""
        self.datemin = float(row[1])

    def _handle_datemax(self, row: pd.Series, name: str) -> None:
        """Handle datemax parameter."""
        self.datemax = float(row[1])

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

        Args:
            date: Single date or array of dates to check

        Returns:
            True if all dates are within [datemin, datemax], False otherwise
        """
        if isinstance(date, np.ndarray):
            return not (any(date > self.datemax) or any(date < self.datemin))
        else:
            return (date <= self.datemax) and (date >= self.datemin)


    def get_concentration(
        self,
        date: Union[float, npt.NDArray[np.float64]],
        time: Union[float, npt.NDArray[np.float64]]
    ) -> Union[float, npt.NDArray[np.float64]]:
        """
        Computes concentrations of tracers.

        Args:
            date: Date(s) at which concentrations are computed.
                date - time = date of recharge for the input chronicle
            time: Time(s) at which concentrations are computed.
                Time necessary for decay and geoproduction

        Returns:
            Concentrations at the given date and time.
            Returns float if inputs are scalars, ndarray if inputs are arrays.
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
                            c1[valid_mask] = self.__recharge_chronicle_interp(date[valid_mask])
                    else:
                        c1 = 0

            elif self.__has_constant_recharge:
                # Constant recharge concentrations, creates vector of the required size
                c1 = self.__recharge_constant * np.ones_like(time)

            # Apply decay to recharge component
            if self.__decay_enabled:
                c1 = c1 * np.exp(-time / self.__decay_time)

            c = c + c1

        # Compute geoproduction component
        if self.__geoproduction_enabled:
            if self.__decay_enabled:
                c2 = self.__geoproduction_rate * (1 - np.exp(-time / self.__decay_time)) * self.__decay_time
            else:
                c2 = self.__geoproduction_rate * time
            c = c + c2

        return c


    def mean_value(self, date: float) -> float:
        """
        Mean value of chronicle taken at date "date".

        Args:
            date: Reference date for computing the mean

        Returns:
            Mean concentration value over the chronicle period
        """
        # Sampling dates
        t = self.datemin + (date - self.datemin) * np.arange(0, 1, 1/1000)
        # Computes convolution
        return float(np.mean(self.get_concentration(t, date - t)))        


    def max_value(self) -> float:
        """
        Max value of recharge chronicle concentrations.

        Returns:
            Maximum concentration value

        Raises:
            ValueError: If tracer has no recharge chronicle
        """
        if not self.__has_chronicle:
            raise ValueError(
                f"Tracer {self.__name} has no recharge chronicle. "
                "max_value() only works with chronicle-based tracers."
            )
        return float(self.__recharge_chronicle_file.iloc[:, 1].max())


    def display(self, display_options: 'DisplayOptions') -> None:
        """
        Display chemical element with plots.

        Args:
            display_options: Display configuration options
        """
        if display_options.text:
            print("chemical:", self.__name)

        # Plotting the input chronicle
        if self.__has_chronicle:
            self.__recharge_chronicle_file.plot(
                x=self.__recharge_chronicle_file.columns[0],
                y=self.__recharge_chronicle_file.columns[1],
                title="input chronicle (recharge) for " + self.__name
            )
            display_options.figure_close_fx(self.__name + "_recharge")

        # extracting the data
        date = np.linspace(self.datemin, self.datemax, 1000)
        time = self.datemax - date
        c = self.get_concentration(date, time)

        # --- Remplacement de figure_init(...) par son contenu ---
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
# Display options configuration
# ------------------------------------------------------
class DisplayOptions:
    """
    Configuration for figure display and saving.

    Attributes:
        text (bool): Enable text output to console
        figure_save (bool): Save figures to disk
        figure_close (bool): Close figures after display
        directory (Path): Output directory for saved figures
    """

    def __init__(
        self,
        text: bool = True,
        figure_save: bool = False,
        figure_close: bool = True,
        directory: Union[Path, str] = "figures_out"
    ) -> None:
        """
        Initialize display options.

        Args:
            text: Enable text output to console
            figure_save: Save figures to disk
            figure_close: Close figures after display
            directory: Output directory for saved figures
        """
        self.text = text
        self.figure_save = figure_save
        self.figure_close = figure_close
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)

    def figure_close_fx(self, filename: str) -> None:
        """
        Save, display, and/or close the current figure.

        Args:
            filename: Base filename (without extension) for saving
        """
        filepath = self.directory / f"{filename}.png"

        if self.figure_save:
            plt.savefig(filepath, dpi=150)
            print(f"Figure saved: {filepath}")

        # Always display on screen
        plt.show()

        # Close if requested
        if self.figure_close:
            plt.close()


def find_tracer_dir() -> Path:
    """
    Find the tracer_data directory relative to this script.

    Returns:
        Path to tracer_data directory

    Raises:
        FileNotFoundError: If tracer_data directory cannot be found

    Note:
        Assumes project structure: .../pyage/sources/tracer/tracer_root.py
        and looks for: .../pyage/sources/tracer_data/
    """
    here = Path(__file__).resolve()

    # Project root: go up from sources/tracer/ to sources/
    project_root = here.parents[1]

    tracer_dir = project_root / "tracer_data"
    if not tracer_dir.exists():
        raise FileNotFoundError(
            f"Tracer data directory not found.\n"
            f"Expected: {tracer_dir}\n"
            f"Script location: {here}"
        )
    return tracer_dir


# ------------------------------------------------------
# Main - Example usage
# ------------------------------------------------------
def main() -> None:
    """
    Main function demonstrating tracer loading and display.

    Loads CFC tracers and displays their recharge chronicles.
    """
    try:
        tracer_dir = find_tracer_dir()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # List of available tracers to demonstrate
    tracer_names = ["cfc11", "cfc12", "cfc113"]

    # Configure display options
    display_options = DisplayOptions(
        text=True,
        figure_save=False,
        figure_close=True
    )

    # Load and display each tracer
    for name in tracer_names:
        print(f"\n{'='*50}")
        print(f"Loading tracer: {name}")
        print(f"{'='*50}")

        try:
            tracer = Tracer(tracer_dir, name=name)
            print(f"  Name: {tracer.name}")
            print(f"  Unit: {tracer.unit}")
            print(f"  Date range: {tracer.datemin} - {tracer.datemax}")
            tracer.display(display_options)

        except (TracerDataError, TracerConfigError) as e:
            print(f"  Error loading tracer '{name}': {e}")


if __name__ == "__main__":
    main()
