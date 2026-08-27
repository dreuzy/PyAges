# -*- coding: utf-8 -*-
# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
Pydantic config models shared by launcher scripts.

Purpose
-------
Centralize YAML schema validation so both launchers stay consistent
and errors are reported early and clearly.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

TEMPORAL_VALID_MODES = {"span", "successive"}


def _resolve_path(value: Path, info):
    root_dir = info.context.get("root_dir") if info.context else None
    if root_dir and not value.is_absolute():
        return Path(root_dir) / value
    return value


class _BaseCfg(BaseModel):
    """Strict base for all user-facing configuration models."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# ---------------------------------------------------------------------------
# CLI config models
# ---------------------------------------------------------------------------


class CliRunParams(_BaseCfg):
    """Validated CLI parameters for `pyages run`."""

    config: Path
    transient: bool = False
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


class CliCheckParams(_BaseCfg):
    """Validated CLI parameters for `pyages check`."""

    verbose: bool = False


# ---------------------------------------------------------------------------
# run_system_check.py (manual integration script) config models
# ---------------------------------------------------------------------------


class SystemCheckConfig(_BaseCfg):
    """Configuration for the integration test script."""

    date: float = 2010
    lpm_all: list[str] = Field(
        default_factory=lambda: [
            "dirac",
            "dirac_double",
            "dirac_double_1_set",
            "exp_shifted",
            "dirac",
            "gamma",
            "exp",
            "uniform",
            "ig",
            "ig_shifted",
            "mix_exp_shifted",
        ]
    )
    lpm_calib: list[str] = Field(
        default_factory=lambda: [
            "dirac_double",
            "exp_shifted",
            "exp",
            "gamma",
            "ig",
            "uniform",
            "dirac_double",
            "dirac",
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


# ---------------------------------------------------------------------------
# Single-date workflow config models
# ---------------------------------------------------------------------------


class LauncherDatasetCfg(_BaseCfg):
    """Dataset section of the single-date launcher YAML."""

    name: str = "example_dataset"
    label: str | None = None
    year: int = 2010
    data_dir: Path = Path("examples/data")
    verbose: bool = True

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path, info):
        return _resolve_path(value, info)


class LauncherLpmCfg(_BaseCfg):
    """LPM section of the single-date launcher YAML."""

    model_name: str = "dirac_double"
    data_directory: Path = Path("data_core/data_lpm")

    @field_validator("data_directory")
    @classmethod
    def _resolve_lpm_dir(cls, value: Path, info):
        return _resolve_path(value, info)


class LauncherTracerCfg(_BaseCfg):
    """Optional tracer data override for single-date launcher workflows."""

    data_directory: Path | None = None

    @field_validator("data_directory")
    @classmethod
    def _resolve_tracer_dir(cls, value: Path | None, info):
        if value is None:
            return None
        return _resolve_path(value, info)


class LauncherRunCfg(_BaseCfg):
    """Run flags for each step of the workflow."""

    reachable_concentrations: bool = True
    objective_function: bool = True
    calibration_metropolis_hastings: bool = True
    calibration_simplex: bool = True


class LauncherReachableCfg(_BaseCfg):
    """Reachable concentrations sampling options."""

    nmodels: int = Field(default=5000, ge=1)


class LauncherObjectiveCfg(_BaseCfg):
    """Objective function sampling options."""

    nmodels: int = Field(default=10000, ge=1)


class LauncherMetropolisCfg(_BaseCfg):
    """Metropolis-Hastings configuration (single-date launcher)."""

    nstep: int = Field(default=5000, ge=1)
    prior_option: bool = False
    likelihood: bool = True
    monitor: bool = False
    display_traj: bool = False


class LauncherSimplexCfg(_BaseCfg):
    """Simplex calibration options."""

    init_multiples_n: int = Field(default=3, ge=1)
    fuq_n: int = Field(default=30, ge=1)


class LauncherConfig(_BaseCfg):
    """Full YAML schema for the single-date workflow."""

    dataset: LauncherDatasetCfg = Field(default_factory=LauncherDatasetCfg)
    lpm: LauncherLpmCfg = Field(default_factory=LauncherLpmCfg)
    tracers: LauncherTracerCfg = Field(default_factory=LauncherTracerCfg)
    run: LauncherRunCfg = Field(default_factory=LauncherRunCfg)
    reachable_concentrations: LauncherReachableCfg = Field(
        default_factory=LauncherReachableCfg
    )
    objective_function: LauncherObjectiveCfg = Field(
        default_factory=LauncherObjectiveCfg
    )
    calibration_metropolis_hastings: LauncherMetropolisCfg = Field(
        default_factory=LauncherMetropolisCfg
    )
    calibration_simplex: LauncherSimplexCfg = Field(default_factory=LauncherSimplexCfg)


class LauncherParams(_BaseCfg):
    """Flattened parameters consumed by the single-date workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str
    dataset_label: str | None
    dataset_year: int
    dataset_data_dir: Path
    verbose: bool
    lpm_model_name: str
    directory_lpm: Path
    tracer_data_dir: Path | None = None
    run_reachable_concentrations: bool
    run_objective_function: bool
    run_calibration_metropolis_hastings: bool
    run_calibration_simplex: bool
    reachable_concentration_nmodels: int
    objective_function_nmodels: int
    mh_nstep: int
    mh_prior_option: bool
    mh_likelihood: bool
    mh_monitor: bool
    mh_display_traj: bool
    simplex_init_multiples_n: int
    simplex_fuq_n: int


# ---------------------------------------------------------------------------
# Generic temporal workflow (multi-date) config models
# ---------------------------------------------------------------------------


class TemporalDatasetCfg(_BaseCfg):
    """Dataset inputs (file path + optional relative error)."""

    file: str = Field(..., min_length=1)
    error_rel: float | None = Field(default=None, ge=0.0, lt=1.0)


class TemporalCalibrationCfg(_BaseCfg):
    """Metropolis-Hastings configuration with bounds and defaults."""

    mh_nsteps: int = Field(default=1000, gt=100)
    burn_in: float = Field(default=0.2, ge=0.0, lt=0.5)
    nskip: int = Field(default=10, ge=1)
    lpm_number: int = Field(default=10, ge=0)
    explo_res: int = Field(default=20, ge=1)
    seed_enabled: bool = False
    seed: int | None = None


class TemporalFiguresCfg(_BaseCfg):
    """Toggle plot outputs."""

    temporal: bool = False
    distributions: bool = False
    concentrations_2d: bool = False


class TemporalWorkflowCfg(_BaseCfg):
    """Workflow control (span vs successive)."""

    mode: str = "span"

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        if value not in TEMPORAL_VALID_MODES:
            raise ValueError(
                f"workflow.mode must be one of {sorted(TEMPORAL_VALID_MODES)}"
            )
        return value


class TemporalLpmModelsCfg(_BaseCfg):
    """LPM selection and optional parameter directory override."""

    list: List[str] | None = None
    directory: str | None = None


class TemporalResultsCfg(_BaseCfg):
    """Results location (default root or explicit directory)."""

    use_default: bool = True
    directory: str | None = None
    study_name: str = Field(
        default="temporal", min_length=1, pattern=r"^[A-Za-z0-9_.-]+$"
    )

    @field_validator("directory")
    @classmethod
    def _require_directory_when_not_default(cls, value: str | None, info):
        if info.data.get("use_default") is False and not value:
            raise ValueError("results.directory must be set when use_default is false.")
        return value


class TemporalParams(_BaseCfg):
    """Top-level configuration for a temporal calibration workflow."""

    dataset: TemporalDatasetCfg
    calibration: TemporalCalibrationCfg = Field(default_factory=TemporalCalibrationCfg)
    figures: TemporalFiguresCfg = Field(default_factory=TemporalFiguresCfg)
    workflow: TemporalWorkflowCfg = Field(default_factory=TemporalWorkflowCfg)
    lpm_models: TemporalLpmModelsCfg = Field(default_factory=TemporalLpmModelsCfg)
    results: TemporalResultsCfg = Field(default_factory=TemporalResultsCfg)


__all__ = [
    "CliRunParams",
    "CliCheckParams",
    "ValidationError",
    "SystemCheckConfig",
    "LauncherConfig",
    "LauncherParams",
    "TemporalParams",
    "TEMPORAL_VALID_MODES",
]
