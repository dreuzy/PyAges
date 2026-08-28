# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Factory utilities for LPM model construction and initialization.

Purpose
-------
Provides the main entry point for creating LPM instances by name.
Uses automatic registration via decorators - new models are discovered
automatically when they use the @register_lpm decorator.

Usage
-----
    from pyages.lpm.factory import build_lpm, list_available_lpms

    # Create an LPM by name
    lpm = build_lpm("ig")

    # List all available models
    print(list_available_lpms())

"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyages.config.paths import DIRECTORY_LPM_DATA
from pyages.lpm.core.registry import (
    UnknownLPMType,
    get_lpm_class,
    is_registered,
    list_available_lpms,
)

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase as LPM


def _resolve_directory(
    directory_lpm: str | Path | None,
) -> str | Path:
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


def build_lpm(
    lpm_type: str,
    directory_lpm: str | Path | None = None,
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
        Defaults to `pyages.config.paths.DIRECTORY_LPM_DATA`.

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
        >>> lpm = build_lpm("ig")
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


def build_random_lpm(
    lpm_type: str,
    rng: Any | None = None,
    directory_lpm: str | Path | None = None,
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
    lpm = build_lpm(lpm_type, directory_lpm)
    lpm.random_uniform(rng)
    return lpm


__all__ = [
    "build_lpm",
    "build_random_lpm",
    "UnknownLPMType",
    "list_available_lpms",
    "is_registered",
]
