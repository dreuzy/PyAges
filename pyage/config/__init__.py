"""Canonical, lazily loaded configuration API for PyAge."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CliCheckParams": ("pyage.config.models", "CliCheckParams"),
    "CliRunParams": ("pyage.config.models", "CliRunParams"),
    "LauncherConfig": ("pyage.config.models", "LauncherConfig"),
    "LauncherParams": ("pyage.config.models", "LauncherParams"),
    "SystemCheckConfig": ("pyage.config.models", "SystemCheckConfig"),
    "TemporalParams": ("pyage.config.models", "TemporalParams"),
    "DIRECTORY_LPM_DATA": ("pyage.config.paths", "DIRECTORY_LPM_DATA"),
    "DIRECTORY_TEST": ("pyage.config.paths", "DIRECTORY_TEST"),
    "DIRECTORY_TRACER_DATA": ("pyage.config.paths", "DIRECTORY_TRACER_DATA"),
    "ROOT_DIRECTORY": ("pyage.config.paths", "ROOT_DIRECTORY"),
    "ROOT_DIRECTORY_RESULTS": ("pyage.config.paths", "ROOT_DIRECTORY_RESULTS"),
    "ROOT_DIRECTORY_SRC": ("pyage.config.paths", "ROOT_DIRECTORY_SRC"),
    "result_subdirectory": ("pyage.config.paths", "result_subdirectory"),
    "timestamp_name": ("pyage.config.paths", "timestamp_name"),
    "DisplayOptions": ("pyage.config.runtime", "DisplayOptions"),
    "SimulationTimer": ("pyage.config.runtime", "SimulationTimer"),
    "arange_n": ("pyage.config.runtime", "arange_n"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load a public configuration symbol only when it is requested."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return module globals together with lazily exported names."""
    return sorted({*globals(), *__all__})
