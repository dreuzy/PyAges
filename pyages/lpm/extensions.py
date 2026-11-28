# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Stable, deliberately small public contract for external LPM packages.

An external package exposes one :class:`LpmDefinition` through the
``pyages.lpms`` entry-point group. The entry-point name is the canonical model
name; the definition only connects the implementation class, its parameter
directory, and the version of this plugin contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

LPM_ENTRY_POINT_GROUP: Final = "pyages.lpms"
LPM_PLUGIN_API_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class LpmDefinition:
    """Declare the stable information PyAges needs to load an external LPM.

    A plugin creates one instance at module level and advertises that object
    through the ``pyages.lpms`` entry-point group. The record contains data
    only: loading policy, conflict handling, parameter validation, model
    construction, and provenance remain PyAges responsibilities.

    Parameters
    ----------
    model_class : type
        Concrete ``LpmBase`` subclass. Its constructor must accept the keyword
        argument ``directory_lpm``.
    parameter_directory : str or pathlib.Path
        Root directory containing ``<entry-point-name>/params.yaml``.
    api_version : int, default=1
        Version of the PyAges plugin contract implemented by the package.

    Notes
    -----
    ``parameter_directory`` names the root, not the model-specific directory.
    For an entry point named ``my_model``, PyAges expects the file
    ``parameter_directory / "my_model" / "params.yaml"``.

    Path normalization happens immediately, but semantic validation is delayed
    until the selected entry point is loaded. This preserves lazy discovery:
    listing installed models never executes third-party model code.
    """

    model_class: type[Any]
    parameter_directory: Path
    api_version: int = LPM_PLUGIN_API_VERSION

    def __post_init__(self) -> None:
        """Store ``parameter_directory`` as a :class:`~pathlib.Path`.

        The registry later verifies the API version, model base class, and
        parameter file after the user selects this plugin. Performing only the
        lossless path conversion here keeps this public record lightweight.
        """
        object.__setattr__(self, "parameter_directory", Path(self.parameter_directory))


@dataclass(frozen=True, slots=True)
class LpmProvenance:
    """Record the exact provider and parameter document used for one LPM.

    Parameters
    ----------
    model_name : str
        Canonical name passed to :func:`pyages.lpm.build_lpm`.
    provider_distribution : str
        Installed Python distribution providing the implementation, or
        ``"pyages"`` for a built-in model.
    provider_version : str
        Installed provider version reported by package metadata.
    entry_point_target : str or None
        Advertised ``module:object`` target for an external provider. Built-in
        models use ``None`` because they are registered inside PyAges.
    plugin_api_version : int
        Version of the external-LPM contract used for construction.
    parameters_sha256 : str
        SHA-256 digest of the exact ``params.yaml`` bytes used by the model.

    Notes
    -----
    The record is immutable and is attached by the factory after successful
    construction. Workflow manifests serialize it so an explicit parameter
    override remains distinguishable from the provider's packaged defaults.
    """

    model_name: str
    provider_distribution: str
    provider_version: str
    entry_point_target: str | None
    plugin_api_version: int
    parameters_sha256: str

    def as_dict(self) -> dict[str, str | int | None]:
        """Return a new JSON-compatible mapping of every provenance field.

        Returns
        -------
        dict
            Plain scalar values suitable for manifest serialization. Mutating
            the returned dictionary cannot modify this immutable record.
        """
        return asdict(self)


__all__ = [
    "LPM_ENTRY_POINT_GROUP",
    "LPM_PLUGIN_API_VERSION",
    "LpmDefinition",
    "LpmProvenance",
]
