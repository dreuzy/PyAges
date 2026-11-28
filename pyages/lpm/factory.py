# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file turns a short model name and optional data directory into an LPM.
# It asks the registry for the matching class, then returns an instance using
# either its configured initial parameters or draws inside calibration ranges.

"""
Factory utilities for LPM model construction and initialization.

Purpose
-------
Provides the main entry point for creating LPM instances by name. Built-ins use
decorator registration; separately installed packages use ``pyages.lpms``
entry points.

Usage
-----
    from pyages.lpm.factory import build_lpm, list_available_lpms

    # Create an LPM by name
    lpm = build_lpm("ig")

    # List all available models
    print(list_available_lpms())

"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from pyages.lpm.core.registry import (
    UnknownLPMType,
    get_lpm_definition,
    is_registered,
    list_available_lpms,
)
from pyages.lpm.extensions import LpmProvenance

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase
    from pyages.lpm.core.registry import ResolvedLpmDefinition


class _LpmConstructor(Protocol):
    """Static constructor shape required from every registered model class.

    Concrete classes may expose additional scientific parameters, but the
    factory always constructs their default state through ``directory_lpm`` so
    YAML initialization and validation follow one common path.
    """

    def __call__(self, *, directory_lpm: str | Path) -> LpmBase:
        """Construct a model whose metadata root has already been selected."""
        ...


def _resolve_directory(
    directory_lpm: str | Path | None,
    default_directory: Path,
) -> Path:
    """Choose the caller's parameter root override or the provider default.

    Parameters
    ----------
    directory_lpm : str or Path or None
        Optional override for LPM data directory.

    default_directory : Path
        Parameter root declared by the selected provider.

    Returns
    -------
    Path
        Effective root expected to contain ``<model-name>/params.yaml``.

    Notes
    -----
    This function establishes precedence only. Existence, schema, parameter
    names, and domains are validated during model construction.
    """
    return Path(directory_lpm) if directory_lpm is not None else default_directory


def _parameters_sha256(directory: Path, model_name: str) -> str:
    """Return the SHA-256 digest of the exact parameter bytes used by a model.

    The digest includes whitespace and comments because it identifies the
    actual input artifact, not merely its parsed numerical values. A missing or
    unreadable file propagates its filesystem exception to the caller.
    """
    path = directory / model_name / "params.yaml"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance_for(
    resolved_definition: ResolvedLpmDefinition,
    directory: Path,
) -> LpmProvenance:
    """Create immutable provenance for one resolved provider and parameter root.

    The caller must pass the same directory used for construction. This keeps
    an explicit study override visible through a different parameter-file hash
    even when provider name and version remain unchanged.
    """
    return LpmProvenance(
        model_name=resolved_definition.name,
        provider_distribution=resolved_definition.provider_distribution,
        provider_version=resolved_definition.provider_version,
        entry_point_target=resolved_definition.entry_point_target,
        plugin_api_version=resolved_definition.definition.api_version,
        parameters_sha256=_parameters_sha256(directory, resolved_definition.name),
    )


def resolve_lpm_parameter_directory(
    lpm_type: str,
    directory_lpm: str | Path | None = None,
) -> Path:
    """Return the parameter root that normal construction would use.

    Parameters
    ----------
    lpm_type : str
        Canonical built-in or external model name.
    directory_lpm : str, pathlib.Path, or None
        Optional caller override. When omitted, use the selected provider's
        packaged parameter root.

    Returns
    -------
    pathlib.Path
        Root expected to contain ``<lpm_type>/params.yaml``.

    Notes
    -----
    Resolving an external model loads and validates its selected entry point,
    but this helper does not instantiate the model or parse the YAML file.
    """
    resolved_definition = get_lpm_definition(lpm_type)
    return _resolve_directory(
        directory_lpm,
        resolved_definition.definition.parameter_directory,
    )


def describe_lpm_provenance(
    lpm_type: str,
    directory_lpm: str | Path | None = None,
) -> LpmProvenance:
    """Describe the selected provider and parameter artifact without a model.

    Parameters
    ----------
    lpm_type : str
        Canonical built-in or external model name.
    directory_lpm : str, pathlib.Path, or None
        Optional parameter-root override subject to normal factory precedence.

    Returns
    -------
    LpmProvenance
        Provider identity, entry-point target, API version, and SHA-256 digest
        of the effective ``params.yaml``.

    Raises
    ------
    LpmRegistryError
        If discovery, conflict resolution, loading, or plugin validation fails.
    OSError
        If the effective parameter file cannot be read for hashing.

    Notes
    -----
    This function does not prove that the YAML schema agrees with the model
    constructor; :func:`build_lpm` performs that integration step.
    """
    resolved_definition = get_lpm_definition(lpm_type)
    resolved_dir = _resolve_directory(
        directory_lpm,
        resolved_definition.definition.parameter_directory,
    )
    return _provenance_for(resolved_definition, resolved_dir)


def build_lpm(
    lpm_type: str,
    directory_lpm: str | Path | None = None,
) -> LpmBase:
    """Construct a built-in or external LPM through the common registry path.

    This is the main construction boundary. It resolves exactly one provider,
    applies caller-over-provider parameter-directory precedence, constructs the
    model so its YAML schema is validated, verifies that the constructed name
    matches the registry name, and attaches immutable provenance.

    Parameters
    ----------
    lpm_type : str
        Name of LPM to generate (e.g., "ig", "exp", "dirac").
        Use list_available_lpms() to see all available types.
    directory_lpm : str or Path or None
        Optional LPM data directory override.
        Defaults to the provider's packaged directory: PyAges data for a
        built-in model or the external package's data for a plugin.

    Returns
    -------
    LpmBase
        Fully initialized model using values from the effective
        ``<lpm_type>/params.yaml`` file.

    Raises
    ------
    UnknownLPMType
        If the requested LPM type is not registered.
    LpmRegistryError
        If providers conflict or an external plugin cannot be loaded or
        validated.
    LPMParamsError
        If the effective parameter document is missing, malformed, or
        inconsistent with the model's constructor parameters.
    ValueError
        If a provider advertised ``lpm_type`` but constructs a differently
        named model.

    Notes
    -----
    External code executes only after its model is selected. Once resolved,
    the plugin definition is cached for the process, but every call returns a
    new model instance.

    Examples
    --------
        >>> lpm = build_lpm("ig")
        >>> print(lpm.name)
        ig
        >>> print(lpm.convolution_strategy)
        ConvolutionStrategy.CONTINUOUS
    """
    resolved_definition = get_lpm_definition(lpm_type)
    lpm_class = cast(
        _LpmConstructor,
        resolved_definition.definition.model_class,
    )
    resolved_dir = _resolve_directory(
        directory_lpm,
        resolved_definition.definition.parameter_directory,
    )
    model = lpm_class(directory_lpm=resolved_dir)
    if model.name != lpm_type:
        raise ValueError(
            f"LPM plugin name mismatch: entry point '{lpm_type}' constructed "
            f"a model named '{model.name}'"
        )
    provenance = _provenance_for(resolved_definition, resolved_dir)
    model._attach_provenance(provenance)
    return model


def build_random_lpm(
    lpm_type: str,
    rng: Any | None = None,
    directory_lpm: str | Path | None = None,
) -> LpmBase:
    """Construct an LPM and draw each parameter within its calibration range.

    Construction, plugin loading, parameter-directory precedence, and
    provenance are identical to :func:`build_lpm`. After construction,
    :meth:`LpmBase.random_uniform` replaces the YAML initial values with a
    uniform draw over each declared calibration interval.

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
    LpmBase
        New model instance with randomized parameters and attached provenance.

    Notes
    -----
    The draw is operational initialization, not a draw from the optional
    scientific prior stored in ``params.yaml``. Pass a seeded NumPy generator
    when reproducibility is required.
    """
    # Build the model first, then randomize its parameters uniformly.
    lpm = build_lpm(lpm_type, directory_lpm)
    lpm.random_uniform(rng)
    return lpm


__all__ = [
    "build_lpm",
    "build_random_lpm",
    "describe_lpm_provenance",
    "resolve_lpm_parameter_directory",
    "UnknownLPMType",
    "list_available_lpms",
    "is_registered",
]
