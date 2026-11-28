# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Discover built-in and installed external LPMs without eager plugin imports.

Built-in models retain their simple ``@register_lpm`` decorator. External
packages advertise definitions through the standard ``pyages.lpms`` entry-point
group. Entry-point metadata is catalogued immediately, but external code is
loaded only when its model is built, inspected explicitly, or checked.

One canonical name may have exactly one provider. A built-in/external or
external/external collision makes that name unusable while leaving unrelated
models available.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, TypeVar, cast

from pyages import __version__
from pyages.config.paths import DIRECTORY_LPM_DATA
from pyages.lpm.extensions import (
    LPM_ENTRY_POINT_GROUP,
    LPM_PLUGIN_API_VERSION,
    LpmDefinition,
)

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase


RegisteredLpm = TypeVar("RegisteredLpm")
_CANONICAL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class LpmCatalogItem:
    """Describe one advertised model without loading external Python code.

    Parameters
    ----------
    name : str
        Entry-point or built-in registration name.
    status : {"available", "conflict", "invalid"}
        Whether the name has one usable provider, several competing providers,
        or syntax incompatible with the canonical ``snake_case`` convention.
    providers : tuple of str
        Human-readable distribution names and versions claiming the name.
    targets : tuple of str
        Corresponding ``module:object`` targets or built-in class addresses.
    built_in : bool
        Whether PyAges itself is one of the providers.

    Notes
    -----
    Catalogue rows intentionally contain metadata only. They are safe for
    ``pyages list lpms`` even when an installed plugin cannot be imported.
    """

    name: str
    status: Literal["available", "conflict", "invalid"]
    providers: tuple[str, ...]
    targets: tuple[str, ...]
    built_in: bool


@dataclass(frozen=True, slots=True)
class ResolvedLpmDefinition:
    """Combine a validated model definition with provider identity.

    The registry creates this record after resolving conflicts and, for an
    external model, loading and validating the selected entry point. The
    factory consumes it to choose parameter data and attach reproducible
    provenance to the constructed model.
    """

    name: str
    definition: LpmDefinition
    provider_distribution: str
    provider_version: str
    entry_point_target: str | None


@dataclass(frozen=True, slots=True)
class _ExternalCandidate:
    """Retain one external advertisement before its target is imported.

    ``entry_point`` supplies the lazy ``load()`` operation. Distribution name
    and version are copied during discovery so listing and conflict messages do
    not need to execute plugin code.
    """

    entry_point: metadata.EntryPoint
    provider_distribution: str
    provider_version: str

    @property
    def target(self) -> str:
        """Return the advertised ``module:object`` address without loading it."""
        return self.entry_point.value


_LPM_REGISTRY: dict[str, type[LpmBase]] = {}
_EXTERNAL_CANDIDATES: dict[str, list[_ExternalCandidate]] = {}
_LOADED_DEFINITIONS: dict[str, ResolvedLpmDefinition] = {}
_builtins_discovered = False
_entry_points_discovered = False


class LpmRegistryError(ValueError):
    """Base class for actionable LPM discovery and loading errors."""


class UnknownLPMType(LpmRegistryError):
    """Report a model name that no usable provider advertises."""


class LpmNameConflict(LpmRegistryError):
    """Report several installed providers claiming one canonical name."""


class LpmPluginLoadError(LpmRegistryError):
    """Report an exception raised while importing one selected plugin."""


class InvalidLpmPlugin(LpmRegistryError):
    """Report a plugin definition that does not satisfy the public contract."""


def _validate_canonical_name(name: str) -> None:
    """Require the single naming convention shared by APIs and entry points.

    A canonical name starts with a lowercase letter and then contains only
    lowercase letters, digits, or underscores. Using one portable spelling for
    registry keys, YAML directories, configuration, and package metadata
    prevents platform-dependent lookup behavior.

    Raises
    ------
    ValueError
        If ``name`` is not a string in canonical ``snake_case`` form.
    """
    if not isinstance(name, str) or _CANONICAL_NAME.fullmatch(name) is None:
        raise ValueError(
            "LPM names must use snake_case: a lowercase letter followed by "
            "lowercase letters, digits, or underscores"
        )


def register_lpm(
    name: str,
) -> Callable[[type[RegisteredLpm]], type[RegisteredLpm]]:
    """Create the decorator that registers one model shipped inside PyAges.

    Parameters
    ----------
    name : str
        Canonical public model name. The same name must be used by the model
        constructor and its ``data_core/data_lpm/<name>/params.yaml`` path.

    Returns
    -------
    callable
        Class decorator that stores the class and returns it unchanged.

    Raises
    ------
    ValueError
        If the name is invalid or another class already owns it.

    Notes
    -----
    External packages must not call this decorator. They advertise an
    :class:`~pyages.lpm.extensions.LpmDefinition` through ``pyages.lpms`` so
    discovery can remain lazy and conflicts can be reported explicitly.
    """
    _validate_canonical_name(name)

    def decorator(cls: type[RegisteredLpm]) -> type[RegisteredLpm]:
        existing = _LPM_REGISTRY.get(name)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"LPM name '{name}' is already registered to {existing.__name__}. "
                f"Cannot register {cls.__name__} with the same name."
            )
        _LPM_REGISTRY[name] = cast("type[LpmBase]", cls)
        return cls

    return decorator


def _discover_builtins() -> None:
    """Import each built-in model module once so its decorator can run.

    The module scan is limited to :mod:`pyages.lpm.models`. The completion flag
    avoids repeated imports on catalogue queries; Python's module cache remains
    the final safeguard against executing a module twice.
    """
    global _builtins_discovered
    if _builtins_discovered:
        return
    import pyages.lpm.models as models_package

    for _, module_name, _ in pkgutil.iter_modules(models_package.__path__):
        importlib.import_module(f"pyages.lpm.models.{module_name}")
    _builtins_discovered = True


def _distribution_identity(entry_point: metadata.EntryPoint) -> tuple[str, str]:
    """Extract provider distribution name and version from entry-point metadata.

    Missing metadata is represented by ``"unknown"`` rather than making the
    whole catalogue unavailable. The entry-point target is not loaded.
    """
    distribution = getattr(entry_point, "dist", None)
    if distribution is None:
        return "unknown", "unknown"
    name = distribution.metadata.get("Name") or getattr(distribution, "name", None)
    version = getattr(distribution, "version", None)
    return str(name or "unknown"), str(version or "unknown")


def _installed_entry_points() -> tuple[metadata.EntryPoint, ...]:
    """Return installed advertisements from the sole supported LPM group.

    Keeping this metadata query behind a function makes discovery testable and
    centralizes the Python 3.12+ :mod:`importlib.metadata` API call.
    """
    return tuple(metadata.entry_points(group=LPM_ENTRY_POINT_GROUP))


def _discover_entry_points() -> None:
    """Cache external advertisements without importing their target modules.

    Candidates are grouped by public name so duplicate providers can be shown
    as a conflict before either provider executes. Repeated discovery calls are
    no-ops for the lifetime of the process unless tests explicitly reset the
    cache.
    """
    global _entry_points_discovered
    if _entry_points_discovered:
        return
    candidates: dict[str, list[_ExternalCandidate]] = {}
    for entry_point in _installed_entry_points():
        provider_name, provider_version = _distribution_identity(entry_point)
        candidates.setdefault(entry_point.name, []).append(
            _ExternalCandidate(
                entry_point=entry_point,
                provider_distribution=provider_name,
                provider_version=provider_version,
            )
        )
    _EXTERNAL_CANDIDATES.clear()
    _EXTERNAL_CANDIDATES.update(candidates)
    _entry_points_discovered = True


def discover_lpms() -> None:
    """Populate the complete process-local LPM catalogue.

    Built-in modules are imported to execute their decorators. External
    packages contribute metadata only at this stage; their code is loaded later
    by :func:`get_lpm_definition` when a specific model is selected.
    """
    _discover_builtins()
    _discover_entry_points()


def _providers_for(name: str) -> tuple[str, ...]:
    """Return display labels for every built-in or external provider of a name."""
    providers: list[str] = []
    if name in _LPM_REGISTRY:
        providers.append(f"pyages {__version__} (built-in)")
    providers.extend(
        f"{candidate.provider_distribution} {candidate.provider_version}"
        for candidate in _EXTERNAL_CANDIDATES.get(name, ())
    )
    return tuple(providers)


def _targets_for(name: str) -> tuple[str, ...]:
    """Return import targets aligned with :func:`_providers_for` output."""
    targets: list[str] = []
    built_in = _LPM_REGISTRY.get(name)
    if built_in is not None:
        targets.append(f"{built_in.__module__}:{built_in.__qualname__}")
    targets.extend(candidate.target for candidate in _EXTERNAL_CANDIDATES.get(name, ()))
    return tuple(targets)


def _has_conflict(name: str) -> bool:
    """Return whether more than one installed provider claims ``name``."""
    return int(name in _LPM_REGISTRY) + len(_EXTERNAL_CANDIDATES.get(name, ())) > 1


def list_lpm_catalog() -> list[LpmCatalogItem]:
    """Return a sorted metadata catalogue including unusable advertisements.

    Returns
    -------
    list of LpmCatalogItem
        One row per distinct advertised name. External targets remain unloaded.

    Notes
    -----
    Unlike :func:`list_available_lpms`, this diagnostic view preserves invalid
    names and conflicts so the CLI can explain why they are unavailable.
    """
    discover_lpms()
    names = sorted(set(_LPM_REGISTRY) | set(_EXTERNAL_CANDIDATES))
    items: list[LpmCatalogItem] = []
    for name in names:
        valid_name = _CANONICAL_NAME.fullmatch(name) is not None
        status: Literal["available", "conflict", "invalid"]
        if not valid_name:
            status = "invalid"
        elif _has_conflict(name):
            status = "conflict"
        else:
            status = "available"
        items.append(
            LpmCatalogItem(
                name=name,
                status=status,
                providers=_providers_for(name),
                targets=_targets_for(name),
                built_in=name in _LPM_REGISTRY,
            )
        )
    return items


def list_available_lpms() -> list[str]:
    """Return sorted names that have exactly one usable provider.

    Reading this list imports built-in modules but does not load external
    entry-point targets. Invalid and conflicting advertisements are omitted and
    remain visible through :func:`list_lpm_catalog`.
    """
    return [item.name for item in list_lpm_catalog() if item.status == "available"]


def _unknown_lpm(name: str) -> UnknownLPMType:
    """Build the standard unknown-model error with current available names."""
    available = ", ".join(list_available_lpms())
    return UnknownLPMType(
        f"Unknown LPM type: '{name}'. Available types: {available or '(none)'}"
    )


def _validate_external_definition(
    name: str,
    candidate: _ExternalCandidate,
    loaded: object,
) -> ResolvedLpmDefinition:
    """Validate a loaded entry-point object and bind its provider metadata.

    Validation covers the public record type, API version, inheritance from
    :class:`LpmBase`, and presence of ``<name>/params.yaml``. Parsing the YAML
    and matching its parameter names are deliberately deferred to normal model
    construction so built-in and external providers use the same path.

    Raises
    ------
    InvalidLpmPlugin
        If any structural requirement of the external-provider contract fails.
    """
    from pyages.lpm.core.lpm_base import LpmBase

    if not isinstance(loaded, LpmDefinition):
        raise InvalidLpmPlugin(
            f"LPM plugin '{name}' from {candidate.provider_distribution} must expose "
            "an instance of pyages.lpm.extensions.LpmDefinition"
        )
    if loaded.api_version != LPM_PLUGIN_API_VERSION:
        raise InvalidLpmPlugin(
            f"LPM plugin '{name}' uses api_version={loaded.api_version}; "
            f"PyAges supports api_version={LPM_PLUGIN_API_VERSION}"
        )
    if not isinstance(loaded.model_class, type) or not issubclass(
        loaded.model_class, LpmBase
    ):
        raise InvalidLpmPlugin(
            f"LPM plugin '{name}' model_class must inherit from LpmBase"
        )
    parameter_directory = Path(loaded.parameter_directory)
    parameter_file = parameter_directory / name / "params.yaml"
    if not parameter_file.is_file():
        raise InvalidLpmPlugin(
            f"LPM plugin '{name}' parameter file is missing: {parameter_file}"
        )
    return ResolvedLpmDefinition(
        name=name,
        definition=loaded,
        provider_distribution=candidate.provider_distribution,
        provider_version=candidate.provider_version,
        entry_point_target=candidate.target,
    )


def get_lpm_definition(name: str) -> ResolvedLpmDefinition:
    """Resolve one model name to a validated, provenance-ready definition.

    The function first discovers metadata, rejects invalid or ambiguous names,
    and returns a process-local cached result when available. Built-in classes
    are wrapped in the same :class:`LpmDefinition` contract used by plugins.
    For an external provider, only the selected entry point is imported and its
    loaded object is validated before caching.

    Parameters
    ----------
    name : str
        Canonical model identifier used in configuration and ``build_lpm``.

    Returns
    -------
    ResolvedLpmDefinition
        Validated definition plus provider distribution, version, and target.

    Raises
    ------
    UnknownLPMType
        If no usable provider advertises ``name`` or its syntax is invalid.
    LpmNameConflict
        If several installed providers claim the same name.
    LpmPluginLoadError
        If importing the selected external target raises an exception.
    InvalidLpmPlugin
        If the loaded entry-point object violates the public plugin contract.
    """
    discover_lpms()
    if _CANONICAL_NAME.fullmatch(name) is None:
        raise _unknown_lpm(name)
    if _has_conflict(name):
        providers = ", ".join(_providers_for(name))
        raise LpmNameConflict(
            f"LPM name '{name}' is provided more than once: {providers}. "
            "Uninstall or rename one provider; PyAges will not choose silently."
        )
    cached = _LOADED_DEFINITIONS.get(name)
    if cached is not None:
        return cached

    built_in = _LPM_REGISTRY.get(name)
    if built_in is not None:
        resolved = ResolvedLpmDefinition(
            name=name,
            definition=LpmDefinition(
                model_class=built_in,
                parameter_directory=DIRECTORY_LPM_DATA,
                api_version=LPM_PLUGIN_API_VERSION,
            ),
            provider_distribution="pyages",
            provider_version=__version__,
            entry_point_target=None,
        )
        _LOADED_DEFINITIONS[name] = resolved
        return resolved

    candidates = _EXTERNAL_CANDIDATES.get(name, ())
    if not candidates:
        raise _unknown_lpm(name)
    candidate = candidates[0]
    try:
        loaded = candidate.entry_point.load()
    except Exception as exc:
        raise LpmPluginLoadError(
            f"Could not load LPM plugin '{name}' from "
            f"{candidate.provider_distribution} ({candidate.target}): {exc}"
        ) from exc
    resolved = _validate_external_definition(name, candidate, loaded)
    _LOADED_DEFINITIONS[name] = resolved
    return resolved


def get_lpm_class(name: str) -> type[LpmBase]:
    """Return the implementation class selected by normal registry rules.

    This compatibility helper has the same discovery, conflict, loading, and
    validation behavior as :func:`get_lpm_definition`, but discards provider
    metadata. New construction code should generally consume the full resolved
    definition through the factory.
    """
    return cast("type[LpmBase]", get_lpm_definition(name).definition.model_class)


def is_registered(name: str) -> bool:
    """Return whether ``name`` currently has exactly one usable provider.

    A duplicate or malformed advertisement returns ``False`` even though it is
    visible in the diagnostic catalogue. External target code is not loaded.
    """
    return name in list_available_lpms()


def _reset_registry_state_for_tests() -> None:
    """Clear external metadata and loaded definitions for isolated tests.

    Built-in registrations remain because their modules stay imported and
    decorators will not run again. This private hook must not be used as a
    runtime plugin-refresh API; restart the process after changing installed
    entry-point metadata.
    """
    global _entry_points_discovered
    _EXTERNAL_CANDIDATES.clear()
    _LOADED_DEFINITIONS.clear()
    _entry_points_discovered = False


__all__ = [
    "InvalidLpmPlugin",
    "LpmCatalogItem",
    "LpmNameConflict",
    "LpmPluginLoadError",
    "LpmRegistryError",
    "ResolvedLpmDefinition",
    "UnknownLPMType",
    "discover_lpms",
    "get_lpm_class",
    "get_lpm_definition",
    "is_registered",
    "list_available_lpms",
    "list_lpm_catalog",
    "register_lpm",
]
