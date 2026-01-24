# -*- coding: utf-8 -*-
"""
Created on Wed Mar 24 22:05:45 2021

@author: Jean-Raynald de Dreuzy

Purpose
-------
Factory utilities for LPM model construction and initialization.
Provides a registry of available LPM types, helpers to resolve model data
directories, and convenience wrappers for randomized parameter initialization.

This module is the main entry point for creating LPM instances by name.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import global_parameters as gp

from LPM.models.LPM_dirac import LPM_dirac
from LPM.models.LPM_dirac_double import LPM_dirac_double
from LPM.models.LPM_dirac_double_1_set import LPM_dirac_double_1_set
from LPM.models.LPM_exp import LPM_exp
from LPM.models.LPM_exp_shifted import LPM_exp_shifted
from LPM.models.LPM_exp_shifted_young import LPM_exp_shifted_young
from LPM.models.LPM_exp_shifted_old import LPM_exp_shifted_old
from LPM.models.LPM_uniform import LPM_uniform
from LPM.models.LPM_ig import LPM_ig
from LPM.models.LPM_ig_shifted import LPM_ig_shifted
from LPM.models.LPM_gamma import LPM_gamma
from LPM.models.LPM_mix_exp_shifted import LPM_mix_exp_shifted


class UnknownLPMType(ValueError):
    """Raised when an LPM type is not registered."""
    pass


_LPM_REGISTRY: Dict[str, Type[Any]] = {
    "exp": LPM_exp,
    "exp_shifted": LPM_exp_shifted,
    "exp_shifted_young": LPM_exp_shifted_young,
    "exp_shifted_old": LPM_exp_shifted_old,
    "mix_exp_shifted": LPM_mix_exp_shifted,
    "dirac": LPM_dirac,
    "dirac_double": LPM_dirac_double,
    "dirac_double_1_set": LPM_dirac_double_1_set,
    "uniform": LPM_uniform,
    "ig": LPM_ig,
    "ig_shifted": LPM_ig_shifted,
    "gamma": LPM_gamma,
}


def _resolve_directory(
    directory_lpm: Optional[Union[str, Path]],
) -> Union[str, Path]:
    """
    Purpose
    -------
    Resolve the LPM data directory with a default fallback.

    Parameters
    ----------
    directory_lpm : str or Path or None
        Optional override for LPM data directory.
    """
    # Prefer explicit directory; fall back to the configured default.
    return directory_lpm if directory_lpm is not None else gp.directory_lpm_data


def _get_lpm_class(lpm_type: str) -> Type[Any]:
    """
    Purpose
    -------
    Return the LPM class registered for the requested type.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to instantiate (e.g., "exp", "dirac").
    """
    # Lookup the class in the registry for the requested model type.
    try:
        return _LPM_REGISTRY[lpm_type]
    except KeyError as exc:
        raise UnknownLPMType(f"Unknown LPM type: {lpm_type}") from exc


def LPM_generate(
    lpm_type: str,
    directory_lpm: Optional[Union[str, Path]] = gp.directory_lpm_data,
) -> Any:
    """
    Purpose
    -------
    Construct an LPM instance for a given model type.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate.
    directory_lpm : str or Path or None
        Optional LPM data directory override.

    Returns
    -------
    LPM
        Lumped parameter model instance.
    """
    # Instantiate the requested LPM class.
    lpm_class = _get_lpm_class(lpm_type)
    return lpm_class(directory_lpm=_resolve_directory(directory_lpm))
        

def LPM_generate_random_uniform(
    lpm_type: str,
    rng: Optional[Any] = None,
    directory_lpm: Optional[Union[str, Path]] = gp.directory_lpm_data,
) -> Any:
    """
    Purpose
    -------
    Construct an LPM instance and sample its parameters uniformly.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate.
    rng : Any, optional
        Random number generator used by the model.
    directory_lpm : str or Path or None
        Optional LPM data directory override.

    Returns
    -------
    LPM
        Lumped parameter model instance with randomized parameters.
    """
    # Build the LPM and randomize parameters uniformly within bounds.
    lpm = LPM_generate(lpm_type, directory_lpm)
    lpm.random_uniform(rng)
    return lpm


def test(lpm_type, display_options):
    """
    Purpose
    -------
    Quick test helper: generate an LPM and display its properties.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate.
    display_options : display_options
        Display configuration for plots and text output.
    """
    # Generate one LPM and display its moments/curves.
    lpm = LPM_generate_random_uniform(lpm_type)
    lpm.moments()
    if display_options.figure:
        lpm.display_pdf_cdf(display_options)
    if display_options.text:
        lpm.display(display_options)
        lpm.display_moments()
        
