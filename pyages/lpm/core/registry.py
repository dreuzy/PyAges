# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Associate LPM configuration names with their implementation classes.

This module is the small indirection layer between user-facing model names
such as ``"ig"`` or ``"dirac"`` and the Python classes that implement those
models.  It stores classes, not model instances: construction and selection
of the parameter-data directory remain the responsibility of
:mod:`pyages.lpm.factory`.

Summary
-------
1. A model module decorates its class with ``@register_lpm("model_name")``.
2. Executing that decorator adds the name-to-class association to the
   process-local ``_LPM_REGISTRY`` dictionary.
3. The first lookup imports every module under :mod:`pyages.lpm.models`.
4. Those imports execute the decorators and therefore populate the registry.
5. Later lookups reuse the populated dictionary without scanning the package
   again.
6. Registering two different classes under one name fails immediately rather
   than silently changing which scientific model a configuration selects.

Why a registry is useful
------------------------
The public factory accepts a short string because model names come from YAML,
command-line arguments, and other data rather than from Python imports.  A
registry translates that external identifier into a class without a long
``if``/``elif`` chain in the factory.  Adding an LPM consequently requires a
new module with a decorated class, but no edit to a central list of models.

Discovery lifecycle
-------------------
Registration is an import-time side effect.  Importing a model module runs its
class decorator; merely importing this registry module does not eagerly load
all model implementations.  :func:`get_lpm_class`,
:func:`list_available_lpms`, and :func:`is_registered` trigger lazy discovery
on first use.  The ``_discovered`` flag makes the package scan idempotent for
the lifetime of the Python process.  If an import fails, the flag is not set,
so the original exception remains visible and a later call may retry.

Typical flow
------------
::

    # In pyages/lpm/models/my_model.py
    @register_lpm("my_model")
    class MyModelLpm(LpmScipy):
        ...

    # In application code; build_lpm delegates the lookup to this registry.
    model = build_lpm("my_model")

"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyages.lpm.core.lpm_base import LpmBase as LPM


# Process-local catalogue. Values are classes so the factory can create a
# fresh, independently parameterized model for every request.
_LPM_REGISTRY: dict[str, type[LPM]] = {}

# Package discovery is lazy and needs to run successfully only once.
_discovered: bool = False


def register_lpm(name: str):
    """Return a class decorator that registers one LPM implementation.

    Decoration happens while the containing model module is imported.  The
    decorated class is returned unchanged, so registration does not alter its
    construction or inheritance behaviour.

    Parameters
    ----------
    name : str
        The name used to identify this LPM (e.g., "ig", "exp", "dirac").
        This name is used by build_lpm() to instantiate the model.

    Returns
    -------
    callable
        Decorator function that registers the class.

    Examples
    --------
    Register a model class with its configuration name::

        @register_lpm("weibull")
        class WeibullLpm(LPMScipySafe):
            scipy_dist = weibull_min
            ...

    Raises
    ------
    ValueError
        If another class already owns ``name``.  Re-registering the same class
        object is harmless; replacing it implicitly is not.
    """

    def decorator(cls: type[LPM]) -> type[LPM]:
        # Never let import order silently decide which implementation wins.
        if name in _LPM_REGISTRY:
            existing = _LPM_REGISTRY[name]
            if existing is not cls:
                raise ValueError(
                    f"LPM name '{name}' is already registered to {existing.__name__}. "
                    f"Cannot register {cls.__name__} with the same name."
                )
        # Store the class itself; instances are created later by build_lpm().
        _LPM_REGISTRY[name] = cls
        return cls

    return decorator


def discover_lpms() -> None:
    """Import all built-in LPM modules to trigger their decorators.

    This function imports all modules in :mod:`pyages.lpm.models`, which causes
    their ``@register_lpm`` decorators to execute and populate the registry.
    It discovers modules from the package rather than maintaining a second,
    manually synchronized list of model names.

    The function is called automatically by all public query operations.  The
    completion flag is deliberately set only after every import succeeds.
    """
    global _discovered
    if _discovered:
        return

    import pyages.lpm.models as models_pkg

    # Importing is the registration operation: each model's class decorator
    # writes its name-to-class association into _LPM_REGISTRY.
    for _, module_name, _ in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"pyages.lpm.models.{module_name}")

    # A failed import exits before this assignment and remains retryable.
    _discovered = True


def get_lpm_class(name: str) -> type[LPM]:
    """Return the LPM implementation class registered under ``name``.

    This function does not instantiate the class.  The public
    :func:`pyages.lpm.factory.build_lpm` factory performs that step after it
    has resolved the parameter-data directory.

    Parameters
    ----------
    name : str
        Name of the LPM model (e.g., "ig", "exp", "dirac").

    Returns
    -------
    Type[LPM]
        The LPM class registered under that name.

    Raises
    ------
    UnknownLPMType
        If no LPM is registered under that name.
    """
    # A lookup must see the complete built-in model catalogue.
    discover_lpms()

    if name not in _LPM_REGISTRY:
        # Reporting the valid keys makes configuration mistakes actionable.
        available = ", ".join(sorted(_LPM_REGISTRY.keys()))
        raise UnknownLPMType(
            f"Unknown LPM type: '{name}'. Available types: {available}"
        )
    return _LPM_REGISTRY[name]


def list_available_lpms() -> list[str]:
    """Return all registered LPM names in deterministic order.

    Returns
    -------
    list[str]
        Sorted list of registered LPM names.
    """
    discover_lpms()
    return sorted(_LPM_REGISTRY.keys())


def is_registered(name: str) -> bool:
    """Return whether ``name`` identifies a discovered LPM class.

    Parameters
    ----------
    name : str
        Name to check.

    Returns
    -------
    bool
        True if registered, False otherwise.
    """
    discover_lpms()
    return name in _LPM_REGISTRY


class UnknownLPMType(ValueError):
    """Report a model name that the runtime registry cannot resolve.

    Subclassing :class:`ValueError` reflects that the registry itself is
    usable, but the supplied configuration value is not among its valid keys.
    """

    pass
