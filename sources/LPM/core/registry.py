# -*- coding: utf-8 -*-
"""
LPM Registry with auto-registration decorator.

Purpose
-------
Provides a plugin-like architecture for LPM models. New models can be
automatically registered by using the @register_lpm decorator, eliminating
the need to manually update a central registry file.

Usage
-----
    from LPM.core.registry import register_lpm

    @register_lpm("my_model")
    class LPM_my_model(LPMScipy):
        ...

Author
------
Jean-Raynald de Dreuzy
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from LPM.core.LPM_root import LPM


# Global registry mapping model names to their classes
_LPM_REGISTRY: Dict[str, Type[LPM]] = {}

# Flag to track if auto-discovery has been performed
_discovered: bool = False


def register_lpm(name: str):
    """
    Decorator to register an LPM class in the global registry.

    Parameters
    ----------
    name : str
        The name used to identify this LPM (e.g., "ig", "exp", "dirac").
        This name is used by lpm_build() to instantiate the model.

    Returns
    -------
    callable
        Decorator function that registers the class.

    Examples
    --------
        @register_lpm("weibull")
        class LPM_weibull(LPMScipySafe):
            scipy_dist = weibull_min
            ...
    """
    def decorator(cls: Type[LPM]) -> Type[LPM]:
        if name in _LPM_REGISTRY:
            existing = _LPM_REGISTRY[name]
            if existing is not cls:
                raise ValueError(
                    f"LPM name '{name}' is already registered to {existing.__name__}. "
                    f"Cannot register {cls.__name__} with the same name."
                )
        _LPM_REGISTRY[name] = cls
        return cls
    return decorator


def discover_lpms() -> None:
    """
    Discover and import all LPM modules to trigger registration.

    This function imports all modules in the LPM.models package,
    which triggers the @register_lpm decorators to execute and
    populate the registry.

    This is called automatically by get_lpm_class() if needed.
    """
    global _discovered
    if _discovered:
        return

    import LPM.models as models_pkg

    # Import all modules in the models package
    for _, module_name, _ in pkgutil.iter_modules(models_pkg.__path__):
        try:
            importlib.import_module(f"LPM.models.{module_name}")
        except ImportError as e:
            # Log but don't fail - allows partial imports
            import warnings
            warnings.warn(f"Failed to import LPM module '{module_name}': {e}")

    _discovered = True


def get_lpm_class(name: str) -> Type[LPM]:
    """
    Get the LPM class registered under the given name.

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
    # Ensure all models are discovered
    discover_lpms()

    if name not in _LPM_REGISTRY:
        available = ", ".join(sorted(_LPM_REGISTRY.keys()))
        raise UnknownLPMType(
            f"Unknown LPM type: '{name}'. "
            f"Available types: {available}"
        )
    return _LPM_REGISTRY[name]


def list_available_lpms() -> list[str]:
    """
    Return a sorted list of all registered LPM names.

    Returns
    -------
    list[str]
        Sorted list of registered LPM names.
    """
    discover_lpms()
    return sorted(_LPM_REGISTRY.keys())


def is_registered(name: str) -> bool:
    """
    Check if an LPM name is registered.

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
    """Raised when an LPM type is not registered."""
    pass
