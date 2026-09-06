# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes validated configuration models, standard paths, and runtime
# helpers through one explicit public API that IDEs and type checkers can inspect.

"""Canonical configuration API for PyAges."""

from __future__ import annotations

from pyages.config.models import (
    CliCheckParams,
    CliRunParams,
    LauncherConfig,
    SystemCheckConfig,
    TemporalParams,
)
from pyages.config.paths import (
    DIRECTORY_LPM_DATA,
    DIRECTORY_TRACER_DATA,
    ROOT_DIRECTORY,
    ROOT_DIRECTORY_RESULTS,
    result_subdirectory,
    timestamp_name,
)
from pyages.config.runtime import DisplayOptions, SimulationTimer, subdivide_interval

__all__ = [
    "CliCheckParams",
    "CliRunParams",
    "LauncherConfig",
    "SystemCheckConfig",
    "TemporalParams",
    "DIRECTORY_LPM_DATA",
    "DIRECTORY_TRACER_DATA",
    "ROOT_DIRECTORY",
    "ROOT_DIRECTORY_RESULTS",
    "result_subdirectory",
    "timestamp_name",
    "DisplayOptions",
    "SimulationTimer",
    "subdivide_interval",
]
