# -*- coding: utf-8 -*-
"""
Factory utilities for LPM model construction and initialization.

Purpose
-------
Provides the main entry point for creating LPM instances by name.
Uses automatic registration via decorators - new models are discovered
automatically when they use the @register_lpm decorator.

Usage
-----
    from pyage.lpm.lpm_build import lpm_build, list_available_lpms

    # Create an LPM by name
    lpm = lpm_build("ig")

    # List all available models
    print(list_available_lpms())

Author
------
Jean-Raynald de Dreuzy
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from pyage.config.paths import DIRECTORY_LPM_DATA
from pyage.lpm.core.registry import (
    UnknownLPMType,
    get_lpm_class,
    is_registered,
    list_available_lpms,
)

if TYPE_CHECKING:
    from pyage.lpm.core.lpm_base import LpmBase as LPM


def _resolve_directory(
    directory_lpm: Optional[Union[str, Path]],
) -> Union[str, Path]:
    """
    Resolve the LPM data directory from an override or the canonical default.

    Parameters
    ----------
    directory_lpm : str or Path or None
        Optional override for LPM data directory.

    Returns
    -------
    str or Path
        Resolved directory path.
    """
    return directory_lpm if directory_lpm is not None else DIRECTORY_LPM_DATA


def lpm_build(
    lpm_type: str,
    directory_lpm: Optional[Union[str, Path]] = None,
) -> "LPM":
    """
    Construct an LPM instance for a given model type.

    This is the main factory function for creating LPM instances.
    Models are automatically discovered via the @register_lpm decorator.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate (e.g., "ig", "exp", "dirac").
        Use list_available_lpms() to see all available types.
    directory_lpm : str or Path or None
        Optional LPM data directory override.
        Defaults to `pyage.config.paths.DIRECTORY_LPM_DATA`.

    Returns
    -------
    LPM
        Lumped parameter model instance.

    Raises
    ------
    UnknownLPMType
        If the requested LPM type is not registered.

    Examples
    --------
        >>> lpm = lpm_build("ig")
        >>> print(lpm.name)
        ig
        >>> print(lpm.convolution_strategy)
        ConvolutionStrategy.CONTINUOUS
    """
    # Resolve the requested model class from the registry.
    lpm_class = get_lpm_class(lpm_type)
    # Resolve the data directory (caller override or configured default).
    resolved_dir = _resolve_directory(directory_lpm)
    # Instantiate the model with its data directory.
    return lpm_class(directory_lpm=resolved_dir)


def lpm_build_random_uniform(
    lpm_type: str,
    rng: Optional[Any] = None,
    directory_lpm: Optional[Union[str, Path]] = None,
) -> "LPM":
    """
    Construct an LPM instance and sample its parameters uniformly.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate.
    rng : numpy.random.Generator, optional
        Random number generator used for sampling.
    directory_lpm : str or Path or None
        Optional LPM data directory override.

    Returns
    -------
    LPM
        Lumped parameter model instance with randomized parameters.
    """
    # Build the model first, then randomize its parameters uniformly.
    lpm = lpm_build(lpm_type, directory_lpm)
    lpm.random_uniform(rng)
    return lpm


def test(lpm_type: str, display_options: Any) -> None:
    """
    Quick test helper: generate an LPM and display its properties.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate.
    display_options : DisplayOptions
        Display configuration for plots and text output.
    """
    # Generate a randomized model instance and compute its summary moments.
    lpm = lpm_build_random_uniform(lpm_type)
    lpm.moments()
    if display_options.figure:
        # Plot PDF/CDF for quick visual inspection.
        lpm.display_pdf_cdf(display_options)
    if display_options.text:
        # Print model details and summary statistics.
        lpm.display(display_options)
        lpm.display_moments()


__all__ = [
    "lpm_build",
    "lpm_build_random_uniform",
    "UnknownLPMType",
    "list_available_lpms",
    "is_registered",
    "test",
]
