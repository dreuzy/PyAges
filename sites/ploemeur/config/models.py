# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Strict configuration models for the Ploemeur workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import (
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from pyages.config._models_base import BaseConfigModel
from pyages.config.models import MetropolisHastingsCfg
from pyages.config.paths import ROOT_DIRECTORY

PLOEMEUR_ROOT = Path(__file__).resolve().parents[1]
TimeSpanMode = Literal[
    "cumulative",
    "successive",
    "span_full",
    "successive_with_prior",
    "span_with_prior",
]


class PloemeurDriverConfig(BaseConfigModel):
    """Configuration for the Ploemeur driver entrypoint."""

    params: Path = Field(
        default_factory=lambda: PLOEMEUR_ROOT / "params" / "ploemeur_full.yaml"
    )

    @field_validator("params")
    @classmethod
    def _resolve_params(cls, value: Path) -> Path:
        path = value if value.is_absolute() else ROOT_DIRECTORY / value
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"Ploemeur params file not found: {path}")
        return path


class WellDateConfig(BaseConfigModel):
    start: int
    end: int

    @model_validator(mode="after")
    def _validate_order(self) -> "WellDateConfig":
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class ObservationMetadataConfig(BaseConfigModel):
    well_dates: dict[str, WellDateConfig] = Field(min_length=1)


class PloemeurObservationsConfig(BaseConfigModel):
    conc_error_rel: list[float] = Field(min_length=1)
    wells: list[str] = Field(min_length=1)
    well_dates: dict[str, WellDateConfig] = Field(default_factory=dict)

    @field_validator("conc_error_rel")
    @classmethod
    def _validate_errors(cls, values: list[float]) -> list[float]:
        if any(value <= 0 or value > 1 for value in values):
            raise ValueError("relative errors must be in the interval (0, 1]")
        return values

    @field_validator("wells")
    @classmethod
    def _validate_wells(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("well names must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("well names must be unique")
        return values


class PloemeurWorkflowSettings(BaseConfigModel):
    breakups: list[int] = Field(default_factory=list, max_length=1)
    prior_pipeline: list[str] = Field(min_length=1)

    @field_validator("breakups")
    @classmethod
    def _validate_breakups(cls, values: list[int]) -> list[int]:
        if values != sorted(set(values)):
            raise ValueError("breakups must be sorted and unique")
        return values

    @field_validator("prior_pipeline")
    @classmethod
    def _validate_pipelines(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("prior-pipeline names must be non-empty")
        if len(values) != len(set(values)):
            raise ValueError("prior-pipeline names must be unique")
        return values


class PloemeurLpmConfig(BaseConfigModel):
    default: list[str] = Field(min_length=1)
    directory: Path
    by_well: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("default")
    @classmethod
    def _validate_default_models(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("LPM names must be non-empty")
        return values

    @field_validator("by_well")
    @classmethod
    def _validate_well_models(
        cls, values: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        empty = [well for well, models in values.items() if not models]
        if empty:
            raise ValueError(f"per-well LPM lists must be non-empty: {empty}")
        return values


class PloemeurCalibrationConfig(BaseConfigModel):
    """Ploemeur preparation, output sampling, and MH controls."""

    exploration_resolution: int = Field(gt=0)
    posterior_draw_count: int = Field(default=0, ge=0)
    metropolis_hastings: MetropolisHastingsCfg


class PloemeurExecutionConfig(BaseConfigModel):
    parallel: bool
    auto_proc_nb: bool
    proc_nb: int = Field(gt=0)


class PloemeurResultsConfig(BaseConfigModel):
    use_default: bool
    directory: str = ""

    @model_validator(mode="after")
    def _validate_directory(self) -> "PloemeurResultsConfig":
        if not self.use_default and not self.directory.strip():
            raise ValueError("directory is required when use_default is false")
        return self


class PloemeurWorkflowConfig(BaseConfigModel):
    workflows: PloemeurWorkflowSettings
    observations: PloemeurObservationsConfig
    lpm_models: PloemeurLpmConfig
    calibration: PloemeurCalibrationConfig
    execution: PloemeurExecutionConfig
    results: PloemeurResultsConfig

    @model_validator(mode="after")
    def _validate_cross_references(self) -> "PloemeurWorkflowConfig":
        unknown_wells = sorted(
            set(self.lpm_models.by_well) - set(self.observations.wells)
        )
        if unknown_wells:
            raise ValueError(
                f"lpm_models.by_well contains wells absent from observations.wells: {unknown_wells}"
            )
        return self


class PriorPipelineStep(BaseConfigModel):
    time_span_and_prior: TimeSpanMode
    prior: bool
    likelihood: bool
    prior_folder: str


class PriorPipelineConfig(BaseConfigModel):
    steps: list[PriorPipelineStep] = Field(min_length=1)
    folder: str


class PriorPipelinePresets(RootModel[dict[str, PriorPipelineConfig]]):
    root: dict[str, PriorPipelineConfig]


__all__ = [
    "ObservationMetadataConfig",
    "PloemeurCalibrationConfig",
    "PloemeurDriverConfig",
    "PloemeurExecutionConfig",
    "PloemeurLpmConfig",
    "PloemeurObservationsConfig",
    "PloemeurResultsConfig",
    "PloemeurWorkflowConfig",
    "PloemeurWorkflowSettings",
    "PriorPipelineConfig",
    "PriorPipelinePresets",
    "PriorPipelineStep",
    "TimeSpanMode",
    "WellDateConfig",
]
