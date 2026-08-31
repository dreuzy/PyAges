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

import builtins
import math
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from pyages.config.paths import validate_path_component

TEMPORAL_VALID_MODES = {"span", "successive"}


def _strict_retained_count(nstep: int, burn_in: float, nskip: int) -> int:
    """Return rows retained by the MH strict burn-in/thinning convention."""
    first = (math.floor((burn_in * nstep) / nskip) + 1) * nskip
    if first >= nstep:
        return 0
    return 1 + (nstep - 1 - first) // nskip


def _maximum_split_ess(chains: int, retained_count: int) -> float:
    """Return Stan's antithetic ESS ceiling after every chain is split."""
    split_draws = chains * 2 * (retained_count // 2)
    return split_draws * math.log10(split_draws)


def _resolve_path(value: Path, info):
    root_dir = info.context.get("root_dir") if info.context else None
    if root_dir and not value.is_absolute():
        return Path(root_dir) / value
    return value


def _reject_boolean_number(value: object, info):
    """Reject YAML booleans before Pydantic can coerce them to zero or one."""
    if isinstance(value, bool):
        raise ValueError(f"{info.field_name} must be numeric, not boolean")
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

    name: str = Field(default="example_dataset", min_length=1)
    label: str | None = None
    year: int = 2010
    data_dir: Path = Path("examples/data")
    verbose: bool = True
    missing_error_rel: float = Field(default=0.01, gt=0.0, lt=1.0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return validate_path_component(value, label="dataset.name")

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, value: Path, info):
        return _resolve_path(value, info)


class LauncherLpmCfg(_BaseCfg):
    """LPM section of the single-date launcher YAML."""

    model_name: str = "dirac_double"
    data_directory: Path = Path("data_core/data_lpm")

    @field_validator("model_name")
    @classmethod
    def _validate_model_name(cls, value: str) -> str:
        return validate_path_component(value, label="lpm.model_name")

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


class MHInitializationCfg(_BaseCfg):
    """Initial-state policy shared by multichain MH workflows."""

    strategy: Literal[
        "prior_sample",
        "bounds_stratified",
        "explicit",
        "model_default",
        "prior_map",
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


class MHPilotCfg(_BaseCfg):
    """Pilot controls used to derive one fixed production proposal."""

    enabled: bool = True
    nstep: int = Field(default=2000, ge=4)
    burn_in: float = Field(default=0.5, ge=0.0, lt=1.0)
    covariance_mode: Literal["pooled_within_chain"] = "pooled_within_chain"
    relative_ridge: float = Field(default=1.0e-6, ge=0.0, allow_inf_nan=False)
    proposal_multiplier: float | Literal["auto"] = "auto"
    save_samples: bool = False

    _strict_numeric_controls = field_validator(
        "nstep",
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
        if self.enabled and _strict_retained_count(self.nstep, self.burn_in, 1) < 2:
            raise ValueError(
                "pilot nstep and burn_in must retain at least two covariance draws"
            )
        return self


class MHDiagnosticsCfg(_BaseCfg):
    """Qualification gates applied to retained production chains."""

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


class MHMultichainCfg(_BaseCfg):
    """Multi-chain controls whose enclosing block activates MH execution."""

    enabled: bool = True
    chains: int = Field(default=4, ge=2)
    master_seed: int | None = Field(default=12345, ge=0)
    initialization: MHInitializationCfg = Field(default_factory=MHInitializationCfg)
    pilot: MHPilotCfg = Field(default_factory=MHPilotCfg)
    diagnostics: MHDiagnosticsCfg = Field(default_factory=MHDiagnosticsCfg)

    _strict_chains = field_validator("chains", mode="before")(_reject_boolean_number)

    @field_validator("master_seed", mode="before")
    @classmethod
    def _reject_boolean_master_seed(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("master_seed must be a non-negative integer or null")
        return value

    @model_validator(mode="after")
    def _require_one_explicit_start_per_chain(self) -> Self:
        starts = self.initialization.explicit_starts
        if starts is not None and len(starts) != self.chains:
            raise ValueError(
                "initialization.explicit_starts must contain one state per chain"
            )
        return self


class LauncherMetropolisCfg(_BaseCfg):
    """Metropolis-Hastings configuration (single-date launcher)."""

    # Eleven transitions are the smallest default-schedule configuration that
    # retains a state under the strict burn-in rule.
    nstep: int = Field(default=5000, ge=11)
    burn_in: float = Field(default=0.2, ge=0.0, lt=1.0)
    nskip: int = Field(default=10, ge=1)
    seed: int = Field(default=12345, ge=0)
    prior_option: bool = False
    likelihood: bool = True
    monitor: bool = False
    display_traj: bool = False
    multichain: MHMultichainCfg | None = None

    _strict_numeric_controls = field_validator(
        "nstep",
        "burn_in",
        "nskip",
        "seed",
        mode="before",
    )(_reject_boolean_number)

    @model_validator(mode="after")
    def _require_multichain_diagnostic_draws(self) -> Self:
        if (
            self.multichain is not None
            and self.multichain.enabled
            and (self.monitor or self.display_traj)
        ):
            raise ValueError(
                "monitor and display_traj are one-chain options; use the saved "
                "per-chain tables for multi-chain trace diagnostics"
            )
        if (
            self.multichain is not None
            and self.multichain.enabled
            and self.multichain.initialization.strategy in {"prior_sample", "prior_map"}
            and not self.prior_option
        ):
            raise ValueError(
                "prior_sample and prior_map initialization require prior_option=true"
            )
        retained_count = _strict_retained_count(self.nstep, self.burn_in, self.nskip)
        if retained_count == 0:
            raise ValueError(
                "nstep, burn_in, and nskip must retain at least one MH draw"
            )
        if (
            self.multichain is not None
            and self.multichain.enabled
            and retained_count < 8
        ):
            raise ValueError(
                "enabled multichain MH must retain at least eight draws per chain"
            )
        if (
            self.multichain is not None
            and self.multichain.enabled
            and self.multichain.diagnostics.require_convergence
        ):
            maximum_ess = _maximum_split_ess(self.multichain.chains, retained_count)
            if (
                self.multichain.diagnostics.min_bulk_ess > maximum_ess
                or self.multichain.diagnostics.min_tail_ess > maximum_ess
            ):
                raise ValueError(
                    "multichain ESS thresholds exceed the maximum split-draw "
                    f"ESS of {maximum_ess:.6g}; increase nstep, reduce thinning, "
                    "or disable required convergence for an exploratory run"
                )
        return self


class LauncherSimplexCfg(_BaseCfg):
    """Simplex calibration options."""

    init_multiples_n: int = Field(default=3, ge=1)
    fuq_n: int = Field(default=30, ge=1)


class LauncherResultsCfg(_BaseCfg):
    """Results location for the single-date launcher workflow."""

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
        return _resolve_path(Path(value), info)

    @field_validator("study_name")
    @classmethod
    def _validate_study_name(cls, value: str) -> str:
        return validate_path_component(value, label="results.study_name")

    @model_validator(mode="after")
    def _require_directory_when_not_default(self) -> Self:
        if not self.use_default and self.directory is None:
            raise ValueError("results.directory must be set when use_default is false.")
        return self


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
    results: LauncherResultsCfg = Field(default_factory=LauncherResultsCfg)


class LauncherParams(_BaseCfg):
    """Flattened parameters consumed by the single-date workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str
    dataset_label: str | None
    dataset_year: int
    dataset_data_dir: Path
    verbose: bool
    missing_error_rel: float
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
    mh_burn_in: float
    mh_nskip: int
    mh_seed: int
    mh_prior_option: bool
    mh_likelihood: bool
    mh_monitor: bool
    mh_display_traj: bool
    mh_multichain: MHMultichainCfg | None
    simplex_init_multiples_n: int
    simplex_fuq_n: int
    results_use_default: bool
    results_directory: Path | None
    results_study_name: str


# ---------------------------------------------------------------------------
# Generic temporal workflow (multi-date) config models
# ---------------------------------------------------------------------------


class TemporalDatasetCfg(_BaseCfg):
    """Dataset inputs (file path + optional relative error)."""

    file: str = Field(..., min_length=1)
    error_rel: float | None = Field(default=None, gt=0.0, lt=1.0)
    missing_error_rel: float = Field(default=0.01, gt=0.0, lt=1.0)


class TemporalCalibrationCfg(_BaseCfg):
    """Metropolis-Hastings configuration with bounds and defaults."""

    mh_nsteps: int = Field(default=1000, gt=100)
    burn_in: float = Field(default=0.2, ge=0.0, lt=0.5)
    nskip: int = Field(default=10, ge=1)
    lpm_number: int = Field(default=10, ge=0)
    explo_res: int = Field(default=20, ge=1)
    seed_enabled: bool = False
    seed: int | None = Field(default=None, ge=0)
    multichain: MHMultichainCfg | None = None

    _strict_numeric_controls = field_validator(
        "mh_nsteps",
        "burn_in",
        "nskip",
        "lpm_number",
        "explo_res",
        "seed",
        mode="before",
    )(_reject_boolean_number)

    @model_validator(mode="after")
    def _require_enabled_seed(self) -> Self:
        multichain_enabled = self.multichain is not None and self.multichain.enabled
        if self.seed_enabled and self.seed is None and not multichain_enabled:
            raise ValueError("calibration.seed is required when seed_enabled is true")
        retained_count = _strict_retained_count(
            self.mh_nsteps, self.burn_in, self.nskip
        )
        if retained_count == 0:
            raise ValueError(
                "mh_nsteps, burn_in, and nskip must retain at least one MH draw"
            )
        if multichain_enabled and retained_count < 8:
            raise ValueError(
                "enabled multichain MH must retain at least eight draws per chain"
            )
        if (
            multichain_enabled
            and self.multichain is not None
            and self.multichain.diagnostics.require_convergence
        ):
            maximum_ess = _maximum_split_ess(self.multichain.chains, retained_count)
            if (
                self.multichain.diagnostics.min_bulk_ess > maximum_ess
                or self.multichain.diagnostics.min_tail_ess > maximum_ess
            ):
                raise ValueError(
                    "multichain ESS thresholds exceed the maximum split-draw "
                    f"ESS of {maximum_ess:.6g}; increase mh_nsteps, reduce thinning, "
                    "or disable required convergence for an exploratory run"
                )
        return self


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

    list: builtins.list[str] | None = None
    directory: str | None = None

    @field_validator("list")
    @classmethod
    def _validate_model_list(
        cls, value: builtins.list[str] | None
    ) -> builtins.list[str] | None:
        if value is None:
            return None
        normalized = [model.strip() for model in value]
        if not normalized or any(not model for model in normalized):
            raise ValueError("lpm_models.list must contain non-empty model names")
        if len(normalized) != len(set(normalized)):
            raise ValueError("lpm_models.list must not contain duplicate models")
        return [
            validate_path_component(model, label="lpm_models.list item")
            for model in normalized
        ]


class TemporalResultsCfg(_BaseCfg):
    """Results location (default root or explicit directory)."""

    use_default: bool = True
    directory: str | None = None
    study_name: str = Field(
        default="temporal", min_length=1, pattern=r"^[A-Za-z0-9_.-]+$"
    )

    @field_validator("study_name")
    @classmethod
    def _validate_study_name(cls, value: str) -> str:
        return validate_path_component(value, label="results.study_name")

    @model_validator(mode="after")
    def _require_directory_when_not_default(self) -> Self:
        if not self.use_default and (
            self.directory is None or not self.directory.strip()
        ):
            raise ValueError("results.directory must be set when use_default is false.")
        return self


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
    "SystemCheckConfig",
    "MHInitializationCfg",
    "MHPilotCfg",
    "MHDiagnosticsCfg",
    "MHMultichainCfg",
    "LauncherConfig",
    "LauncherParams",
    "LauncherResultsCfg",
    "TemporalParams",
    "TEMPORAL_VALID_MODES",
]
