# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical, lazily loaded configuration API for PyAges."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CliCheckParams": ("pyages.config.models", "CliCheckParams"),
    "CliRunParams": ("pyages.config.models", "CliRunParams"),
    "LauncherConfig": ("pyages.config.models", "LauncherConfig"),
    "LauncherParams": ("pyages.config.models", "LauncherParams"),
    "SystemCheckConfig": ("pyages.config.models", "SystemCheckConfig"),
    "TemporalParams": ("pyages.config.models", "TemporalParams"),
    "DIRECTORY_LPM_DATA": ("pyages.config.paths", "DIRECTORY_LPM_DATA"),
    "DIRECTORY_TEST": ("pyages.config.paths", "DIRECTORY_TEST"),
    "DIRECTORY_TRACER_DATA": ("pyages.config.paths", "DIRECTORY_TRACER_DATA"),
    "ROOT_DIRECTORY": ("pyages.config.paths", "ROOT_DIRECTORY"),
    "ROOT_DIRECTORY_RESULTS": ("pyages.config.paths", "ROOT_DIRECTORY_RESULTS"),
    "ROOT_DIRECTORY_SRC": ("pyages.config.paths", "ROOT_DIRECTORY_SRC"),
    "result_subdirectory": ("pyages.config.paths", "result_subdirectory"),
    "timestamp_name": ("pyages.config.paths", "timestamp_name"),
    "DisplayOptions": ("pyages.config.runtime", "DisplayOptions"),
    "SimulationTimer": ("pyages.config.runtime", "SimulationTimer"),
    "subdivide_interval": ("pyages.config.runtime", "subdivide_interval"),
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
