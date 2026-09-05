# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines typed settings used only by command-line operations.

"""Validate parsed options for workflow launch and installation checks.

The models convert command-line paths, workflow selectors, LPM names, and manual
integration limits into the types expected by command implementations. Missing
configuration files, empty identifiers, invalid counts, and unavailable model
selections are rejected before command dispatch.

The live LPM registry is resolved lazily when check defaults are needed, avoiding
an eager scientific-model import during general configuration loading.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator

from pyages.config._models_base import BaseConfigModel


def registered_lpm_names() -> list[str]:
    """Resolve the live LPM registry lazily for integration-check defaults."""
    from pyages.lpm.core.registry import list_available_lpms

    return list_available_lpms()


class CliRunParams(BaseConfigModel):
    """Validated CLI parameters for ``pyages run``."""

    config: Path
    inline: bool = False
    verbose: bool = False
    lpm: str | None = None
    mh_nsteps: int | None = None
    data_name: str | None = None
    data_dir: Path | None = None
    data_file: Path | None = None

    @field_validator("config")
    @classmethod
    def _config_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"Config file not found: {value}")
        return value

    @field_validator("lpm")
    @classmethod
    def _lpm_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("lpm must be a non-empty string")
        return value

    @field_validator("mh_nsteps")
    @classmethod
    def _mh_nsteps_positive(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("mh_nsteps must be > 0")
        return value

    @field_validator("data_name")
    @classmethod
    def _data_name_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("data_name must be a non-empty string")
        return value


class CliCheckParams(BaseConfigModel):
    """Validated CLI parameters for ``pyages check``."""

    verbose: bool = False


class SystemCheckConfig(BaseConfigModel):
    """Configuration for the manual integration test script."""

    date: float = 2010
    lpm_all: list[str] = Field(default_factory=registered_lpm_names)
    lpm_calib: list[str] = Field(
        default_factory=lambda: [
            "dirac_double",
            "exp_shifted",
            "exp",
            "gamma",
            "ig",
            "uniform",
            "dirac",
            "weibull",
        ]
    )
    tracers_all: list[str] = Field(
        default_factory=lambda: [
            "Li",
            "sf6",
            "cfc11",
            "cfc12",
            "cfc113",
            "kr85",
            "3H",
            "14C",
            "39Ar",
        ]
    )
    tracers_conv: list[str] = Field(default_factory=lambda: ["cfc11", "kr85"])
    tracers_calib: list[str] = Field(default_factory=lambda: ["cfc11", "kr85"])
    reachable_resolution: int = Field(default=1000, ge=1)

    @field_validator("lpm_all", "lpm_calib")
    @classmethod
    def _validate_lpm_lists(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("LPM integration-check lists must not contain duplicates")
        unknown = sorted(set(value).difference(registered_lpm_names()))
        if unknown:
            raise ValueError(f"Unknown LPM names in integration-check list: {unknown}")
        return value


__all__ = ["CliCheckParams", "CliRunParams", "SystemCheckConfig"]
