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
    from LPM.LPM_generate import LPM_generate, list_available_lpms

    # Create an LPM by name
    lpm = LPM_generate("ig")

    # List all available models
    print(list_available_lpms())

Author
------
Jean-Raynald de Dreuzy
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import global_parameters as gp

from LPM.core.registry import (
    UnknownLPMType,
    get_lpm_class,
    list_available_lpms,
    is_registered,
)

if TYPE_CHECKING:
    from LPM.core.LPM_root import LPM


def _resolve_directory(
    directory_lpm: Optional[Union[str, Path]],
) -> Union[str, Path]:
    """
    Resolve the LPM data directory with a default fallback.

    Parameters
    ----------
    directory_lpm : str or Path or None
        Optional override for LPM data directory.

    Returns
    -------
    str or Path
        Resolved directory path.
    """
    return directory_lpm if directory_lpm is not None else gp.DIRECTORY_LPM_DATA


def LPM_generate(
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
        Defaults to gp.DIRECTORY_LPM_DATA.

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
        >>> lpm = LPM_generate("ig")
        >>> print(lpm.name)
        ig
        >>> print(lpm.convolution_strategy)
        ConvolutionStrategy.CLASSIC
    """
    lpm_class = get_lpm_class(lpm_type)
    resolved_dir = _resolve_directory(directory_lpm)
    return lpm_class(directory_lpm=resolved_dir)


def LPM_generate_random_uniform(
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
    lpm = LPM_generate(lpm_type, directory_lpm)
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
    lpm = LPM_generate_random_uniform(lpm_type)
    lpm.moments()
    if display_options.figure:
        lpm.display_pdf_cdf(display_options)
    if display_options.text:
        lpm.display(display_options)
        lpm.display_moments()


# Re-export for backward compatibility
__all__ = [
    "LPM_generate",
    "LPM_generate_random_uniform",
    "UnknownLPMType",
    "list_available_lpms",
    "is_registered",
    "test",
]
