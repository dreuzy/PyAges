# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the validated configuration schemas used by PyAges workflows.

"""Convert workflow YAML mappings into strict, typed Pydantic configuration.

The models describe datasets, LPMs, tracers, calibration methods, diagnostic
settings, figures, and result locations for both single-date and temporal runs.
Nested sections are validated before workflow code accesses them. The Python
objects deliberately use the same section names as schema-3 YAML files so a
developer does not have to learn a second, internal configuration vocabulary.

Cross-field validators also reject combinations that are individually valid but
cannot form a coherent run, such as incomplete multi-chain settings or mutually
inconsistent method options. This module validates configuration structure; it
does not load scientific datasets or execute a calibration.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from pyages.config._models_base import BaseConfigModel
from pyages.config._models_base import (
    reject_boolean_number as _reject_boolean_number,
)
from pyages.config._models_base import (
    resolve_path as _resolve_path,
)
from pyages.config._models_cli import CliCheckParams, CliRunParams, SystemCheckConfig
from pyages.config.paths import DIRECTORY_LPM_DATA, validate_path_component
from pyages.config.sampling_schedule import (
    maximum_split_ess,
    strict_retained_sample_count,
)

TEMPORAL_VALID_MODES = {"span", "successive"}
CONFIGURATION_SCHEMA_VERSION = 3


# ---------------------------------------------------------------------------
# Single-date workflow config models
# ---------------------------------------------------------------------------


class SingleDateDataCfg(BaseConfigModel):
    """Data section of a single-date workflow configuration."""

    name: str = Field(default="example_dataset", min_length=1)
    label: str | None = None
    year: int = 2010
    data_dir: Path = Path("examples/data")
    verbose: bool = True
    missing_error_rel: float = Field(default=0.01, gt=0.0, lt=1.0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_path_component(value, label="data.name")

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path, info):
        return _resolve_path(value, info)


class SingleDateLpmCfg(BaseConfigModel):
    """Single selected LPM and its parameter directory."""

    models: list[str] = Field(default_factory=lambda: ["dirac_double"])
    directory: Path = Field(default_factory=lambda: DIRECTORY_LPM_DATA)

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: list[str]) -> list[str]:
        if len(value) != 1:
            raise ValueError("single_date lpm.models must contain exactly one model")
        model = value[0].strip()
        return [validate_path_component(model, label="lpm.models item")]

    @field_validator("directory")
    @classmethod
    def _resolve_lpm_dir(cls, value: Path, info):
        return _resolve_path(value, info)


class SingleDateTracerCfg(BaseConfigModel):
    """Optional tracer data override for single-date launcher workflows."""

    data_directory: Path | None = None

    @field_validator("data_directory")
    @classmethod
    def _resolve_tracer_dir(cls, value: Path | None, info):
        if value is None:
            return None
        return _resolve_path(value, info)


class SingleDateRunCfg(BaseConfigModel):
    """Run flags for each step of the workflow."""

    reachable_concentrations: bool = True
    objective_function: bool = True
    metropolis_hastings: bool = True
    simplex: bool = True


class SingleDateReachableCfg(BaseConfigModel):
    """Reachable concentrations sampling options."""

    nmodels: int = Field(default=5000, ge=1)


class SingleDateObjectiveCfg(BaseConfigModel):
    """Objective function sampling options."""

    nmodels: int = Field(default=10000, ge=1)


class MHInitializationCfg(BaseConfigModel):
    """Initial-state policy shared by every MH workflow.

    The default ``bounds_stratified`` policy has the same meaning for one or
    several chains. Use ``explicit`` when a study requires fixed starts.
    """

    strategy: Literal[
        "prior_sample",
        "bounds_stratified",
        "explicit",
    ] = "bounds_stratified"
    explicit_starts: list[dict[str, float]] | None = None
    max_attempts: int = Field(default=100, ge=1)

    _strict_max_attempts = field_validator("max_attempts", mode="before")(
        _reject_boolean_number
    )

    @field_validator("explicit_starts", mode="before")
    @classmethod
    def _reject_boolean_explicit_values(cls, value: object) -> object:
        if value is None:
            return value
        if not isinstance(value, list):
            return value
        for chain_index, state in enumerate(value, start=1):
            if not isinstance(state, dict):
                continue
            boolean_names = [
                name for name, item in state.items() if isinstance(item, bool)
            ]
            if boolean_names:
                raise ValueError(
                    "initialization.explicit_starts contains boolean parameter "
                    f"values in chain {chain_index}: {boolean_names}"
                )
        return value

    @model_validator(mode="after")
    def _validate_explicit_starts(self) -> Self:
        if self.strategy == "explicit" and not self.explicit_starts:
            raise ValueError(
                "initialization.explicit_starts is required for the explicit strategy"
            )
        if self.strategy != "explicit" and self.explicit_starts is not None:
            raise ValueError(
                "initialization.explicit_starts is accepted only for the explicit "
                "strategy"
            )
        return self


class MHPilotCfg(BaseConfigModel):
    """Pilot controls used to derive one fixed production proposal.

    Retained, unthinned pilot draws estimate a covariance after separate
    within-chain centering. ``relative_ridge`` regularizes that covariance and
    ``proposal_multiplier='auto'`` selects ``2.38 / sqrt(dimension)``. Pilot
    draws are excluded from the posterior and saved only when requested.
    """

    enabled: bool = False
    nsteps: int = Field(default=2000, ge=4)
    burn_in: float = Field(default=0.5, ge=0.0, lt=1.0)
    relative_ridge: float = Field(default=1.0e-6, ge=0.0, allow_inf_nan=False)
    proposal_multiplier: float | Literal["auto"] = "auto"
    save_samples: bool = False

    _strict_numeric_controls = field_validator(
        "nsteps",
        "burn_in",
        "relative_ridge",
        mode="before",
    )(_reject_boolean_number)

    @field_validator("proposal_multiplier", mode="before")
    @classmethod
    def _validate_proposal_multiplier(
        cls, value: float | Literal["auto"]
    ) -> float | Literal["auto"]:
        if value == "auto":
            return value
        if isinstance(value, bool):
            raise ValueError("pilot.proposal_multiplier must not be boolean")
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("pilot.proposal_multiplier must be positive or 'auto'")
        return value

    @model_validator(mode="after")
    def _require_covariance_draws(self) -> Self:
        if (
            self.enabled
            and strict_retained_sample_count(self.nsteps, self.burn_in, 1) < 2
        ):
            raise ValueError(
                "pilot nsteps and burn_in must retain at least two covariance draws"
            )
        return self


class MHDiagnosticsCfg(BaseConfigModel):
    """Qualification gates applied to retained production chains.

    Qualification requires R-hat strictly below ``max_rhat``, both ESS values
    at or above their minima, and a finite mean MCSE. Disabling
    ``require_convergence`` permits explicit exploratory pooling but does not
    skip diagnostic calculation or persistence.
    """

    max_rhat: float = Field(default=1.01, gt=1.0, allow_inf_nan=False)
    min_bulk_ess: float = Field(default=300.0, gt=0.0, allow_inf_nan=False)
    min_tail_ess: float = Field(default=300.0, gt=0.0, allow_inf_nan=False)
    require_convergence: bool = True

    _strict_numeric_thresholds = field_validator(
        "max_rhat",
        "min_bulk_ess",
        "min_tail_ess",
        mode="before",
    )(_reject_boolean_number)


class MetropolisHastingsCfg(BaseConfigModel):
    """Complete, unambiguous controls for a one-to-many-chain MH run.

    The same fields and runner are used for one or several chains. Inter-chain
    diagnostics apply only when ``chains >= 2``. ``seed=None`` requests a new
    random master seed, which is recorded with the result for replay.
    """

    nsteps: int = Field(default=5000, ge=1)
    burn_in: float = Field(default=0.2, ge=0.0, lt=1.0)
    thinning: int = Field(default=10, ge=1)
    seed: int | None = Field(default=12345, ge=0)
    chains: int = Field(default=1, ge=1)
    prior_option: bool = False
    likelihood: bool = True
    display_traj: bool = False
    initialization: MHInitializationCfg = Field(default_factory=MHInitializationCfg)
    pilot: MHPilotCfg = Field(default_factory=MHPilotCfg)
    diagnostics: MHDiagnosticsCfg = Field(default_factory=MHDiagnosticsCfg)

    _strict_numeric_controls = field_validator(
        "nsteps",
        "burn_in",
        "thinning",
        "seed",
        "chains",
        mode="before",
    )(_reject_boolean_number)

    @model_validator(mode="after")
    def _validate_run_schedule(self) -> Self:
        """Reject schedules that cannot provide the requested diagnostics."""
        starts = self.initialization.explicit_starts
        if starts is not None and len(starts) != self.chains:
            raise ValueError(
                "initialization.explicit_starts must contain one state per chain"
            )
        retained_count = strict_retained_sample_count(
            self.nsteps, self.burn_in, self.thinning
        )
        if retained_count == 0:
            raise ValueError(
                "nsteps, burn_in, and thinning must retain at least one MH draw"
            )
        if self.chains > 1 and retained_count < 8:
            raise ValueError(
                "MH with several chains must retain at least eight draws per chain"
            )
        if self.chains > 1 and self.diagnostics.require_convergence:
            maximum_ess = maximum_split_ess(self.chains, retained_count)
            if (
                self.diagnostics.min_bulk_ess > maximum_ess
                or self.diagnostics.min_tail_ess > maximum_ess
            ):
                raise ValueError(
                    "MH ESS thresholds exceed the maximum split-draw ESS of "
                    f"{maximum_ess:.6g}; increase nsteps, reduce thinning, or "
                    "disable required convergence for an exploratory run"
                )
        if self.initialization.strategy == "prior_sample" and not self.prior_option:
            raise ValueError("prior_sample initialization requires prior_option=true")
        return self


class SingleDateSimplexCfg(BaseConfigModel):
    """Simplex calibration options."""

    init_multiples_n: int = Field(default=3, ge=1)
    fuq_n: int = Field(default=30, ge=1)


class SingleDateOutputCfg(BaseConfigModel):
    """Output location for a single-date workflow."""

    use_default: bool = True
    directory: Path | None = None
    study_name: str = Field(
        default="test_cases", min_length=1, pattern=r"^[A-Za-z0-9_.-]+$"
    )

    @field_validator("directory", mode="before")
    @classmethod
    def _resolve_results_directory(cls, value: object, info):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not isinstance(value, (str, Path)):
            raise ValueError("output.directory must be a path or null")
        return _resolve_path(Path(value), info)

    @field_validator("study_name")
    @classmethod
    def _validate_study_name(cls, value: str) -> str:
        return validate_path_component(value, label="output.study_name")

    @model_validator(mode="after")
    def _require_directory_when_not_default(self) -> Self:
        if not self.use_default and self.directory is None:
            raise ValueError("output.directory must be set when use_default is false.")
        return self


class SingleDateCalibrationCfg(BaseConfigModel):
    """Calibration methods available to a single-date workflow."""

    metropolis_hastings: MetropolisHastingsCfg = Field(
        default_factory=MetropolisHastingsCfg
    )
    simplex: SingleDateSimplexCfg = Field(default_factory=SingleDateSimplexCfg)


class SingleDateWorkflowCfg(BaseConfigModel):
    """Workflow discriminator used by the command line."""

    kind: Literal["single_date"]


class SingleDateConfig(BaseConfigModel):
    """Full YAML schema for the single-date workflow."""

    schema_version: Literal[3]
    workflow: SingleDateWorkflowCfg
    data: SingleDateDataCfg = Field(default_factory=SingleDateDataCfg)
    lpm: SingleDateLpmCfg = Field(default_factory=SingleDateLpmCfg)
    tracers: SingleDateTracerCfg = Field(default_factory=SingleDateTracerCfg)
    run: SingleDateRunCfg = Field(default_factory=SingleDateRunCfg)
    reachable_concentrations: SingleDateReachableCfg = Field(
        default_factory=SingleDateReachableCfg
    )
    objective_function: SingleDateObjectiveCfg = Field(
        default_factory=SingleDateObjectiveCfg
    )
    calibration: SingleDateCalibrationCfg = Field(
        default_factory=SingleDateCalibrationCfg
    )
    output: SingleDateOutputCfg = Field(default_factory=SingleDateOutputCfg)


# ---------------------------------------------------------------------------
# Generic temporal workflow (multi-date) config models
# ---------------------------------------------------------------------------


class TemporalDataCfg(BaseConfigModel):
    """Dataset inputs (file path + optional relative error)."""

    file: str = Field(..., min_length=1)
    error_rel: float | None = Field(default=None, gt=0.0, lt=1.0)
    missing_error_rel: float = Field(default=0.01, gt=0.0, lt=1.0)


class TemporalReportingCfg(BaseConfigModel):
    """Toggle plot outputs."""

    temporal: bool = False
    distributions: bool = False
    concentrations_2d: bool = False


class TemporalWorkflowCfg(BaseConfigModel):
    """Workflow control (span vs successive)."""

    kind: Literal["temporal"]
    mode: str = "span"

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        if value not in TEMPORAL_VALID_MODES:
            raise ValueError(
                f"workflow.mode must be one of {sorted(TEMPORAL_VALID_MODES)}"
            )
        return value


class TemporalLpmCfg(BaseConfigModel):
    """LPM selection and optional parameter directory override."""

    models: list[str] | None = None
    directory: str | None = None

    @field_validator("models")
    @classmethod
    def _validate_model_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [model.strip() for model in value]
        if not normalized or any(not model for model in normalized):
            raise ValueError("lpm.models must contain non-empty model names")
        if len(normalized) != len(set(normalized)):
            raise ValueError("lpm.models must not contain duplicate models")
        return [
            validate_path_component(model, label="lpm.models item")
            for model in normalized
        ]


class TemporalOutputCfg(BaseConfigModel):
    """Results location (default root or explicit directory)."""

    use_default: bool = True
    directory: str | None = None
    study_name: str = Field(
        default="temporal", min_length=1, pattern=r"^[A-Za-z0-9_.-]+$"
    )

    @field_validator("study_name")
    @classmethod
    def _validate_study_name(cls, value: str) -> str:
        return validate_path_component(value, label="output.study_name")

    @model_validator(mode="after")
    def _require_directory_when_not_default(self) -> Self:
        if not self.use_default and (
            self.directory is None or not self.directory.strip()
        ):
            raise ValueError("output.directory must be set when use_default is false.")
        return self


class TemporalCalibrationCfg(BaseConfigModel):
    """Inference and temporal sampling controls for a temporal workflow."""

    exploration_resolution: int = Field(default=20, ge=1)
    posterior_draw_count: int = Field(default=10, ge=0)
    metropolis_hastings: MetropolisHastingsCfg = Field(
        default_factory=MetropolisHastingsCfg
    )

    _strict_numeric_controls = field_validator(
        "exploration_resolution",
        "posterior_draw_count",
        mode="before",
    )(_reject_boolean_number)


class TemporalConfig(BaseConfigModel):
    """Top-level configuration for a temporal calibration workflow."""

    schema_version: Literal[3]
    data: TemporalDataCfg
    calibration: TemporalCalibrationCfg = Field(default_factory=TemporalCalibrationCfg)
    reporting: TemporalReportingCfg = Field(default_factory=TemporalReportingCfg)
    workflow: TemporalWorkflowCfg
    lpm: TemporalLpmCfg = Field(default_factory=TemporalLpmCfg)
    output: TemporalOutputCfg = Field(default_factory=TemporalOutputCfg)


__all__ = [
    "CliRunParams",
    "CliCheckParams",
    "CONFIGURATION_SCHEMA_VERSION",
    "SystemCheckConfig",
    "MHInitializationCfg",
    "MHPilotCfg",
    "MHDiagnosticsCfg",
    "MetropolisHastingsCfg",
    "SingleDateConfig",
    "SingleDateCalibrationCfg",
    "SingleDateDataCfg",
    "SingleDateLpmCfg",
    "SingleDateObjectiveCfg",
    "SingleDateReachableCfg",
    "SingleDateOutputCfg",
    "SingleDateRunCfg",
    "SingleDateSimplexCfg",
    "SingleDateTracerCfg",
    "SingleDateWorkflowCfg",
    "TemporalConfig",
    "TemporalDataCfg",
    "TemporalCalibrationCfg",
    "TemporalReportingCfg",
    "TemporalLpmCfg",
    "TemporalOutputCfg",
    "TEMPORAL_VALID_MODES",
]
