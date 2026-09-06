# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file translates versioned user configuration into the workflow-specific
# runtime schemas and upgrades legacy 1.x mappings without changing semantics.

"""Version and migrate user-facing workflow configuration.

PyAges 1.2 introduces configuration schema 2.  Its common top-level sections
(``data``, ``lpm``, ``calibration``, ``reporting``, and ``output``) are
translated at the input boundary so the established scientific workflow models
remain unchanged.  Unversioned 1.x files continue to run and can be converted
explicitly with the CLI migration command.
"""

from __future__ import annotations

import copy
import os
import warnings
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypeAlias, cast

from pyages.config.paths import DIRECTORY_LPM_DATA

CONFIGURATION_SCHEMA_VERSION = 2

WorkflowKind: TypeAlias = Literal["single_date", "temporal"]


class LegacyConfigurationWarning(DeprecationWarning):
    """Warn that an unversioned 1.x file uses the legacy section layout."""


def configuration_workflow_kind(payload: Mapping[str, Any]) -> WorkflowKind:
    """Return the explicitly declared workflow kind from a configuration."""
    workflow = payload.get("workflow")
    declared = workflow.get("kind") if isinstance(workflow, Mapping) else None
    if declared not in {"single_date", "temporal"}:
        raise ValueError(
            "workflow.kind is required and must be 'single_date' or 'temporal'"
        )
    return cast(WorkflowKind, declared)


def is_legacy_configuration(payload: Mapping[str, Any]) -> bool:
    """Return whether a mapping uses the unversioned PyAges 1.x layout."""
    return "schema_version" not in payload


def configuration_base_directory(
    path: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    """Return the path base promised by the selected configuration schema.

    Schema 2 is self-contained and always resolves relative paths beside its
    YAML file. Legacy source-checkout configurations retain the historical
    checkout-root behavior.
    """
    source = Path(path).resolve()
    if payload.get("schema_version") == CONFIGURATION_SCHEMA_VERSION:
        return source.parent
    from pyages.config.paths import configuration_root

    return configuration_root(source)


def normalize_configuration_payload(
    payload: Mapping[str, Any],
    *,
    expected_kind: WorkflowKind | None = None,
    warn_legacy: bool = True,
) -> dict[str, Any]:
    """Translate schema 2 or pass through a compatible legacy 1.x mapping.

    The returned mapping is a deep copy and can therefore be changed safely by
    command-line overrides.  Unknown keys are deliberately preserved for the
    strict Pydantic runtime models to reject.
    """
    data = copy.deepcopy(dict(payload))
    version = data.get("schema_version")
    if version is None and "schema_version" not in data:
        kind = _legacy_workflow_kind(data, expected_kind)
        _normalize_legacy_aliases(data, kind)
        if warn_legacy:
            warnings.warn(
                "Unversioned PyAges 1.x configuration syntax remains supported "
                "in 1.2; run 'pyages config migrate SOURCE DESTINATION' to use "
                "schema_version: 2.",
                LegacyConfigurationWarning,
                stacklevel=2,
            )
        return data
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("schema_version must be the integer 2")
    if version != CONFIGURATION_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported configuration schema_version "
            f"{version}; expected {CONFIGURATION_SCHEMA_VERSION}"
        )
    data.pop("schema_version")
    kind = configuration_workflow_kind(data)
    if expected_kind is not None and kind != expected_kind:
        raise ValueError(f"Expected a {expected_kind} configuration, received {kind}")
    return _canonical_to_runtime(data, kind)


def migrate_configuration_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a schema-2 mapping with the same workflow settings as ``payload``."""
    data = copy.deepcopy(dict(payload))
    if not is_legacy_configuration(data):
        # Validate the version and canonical spelling before returning a copy.
        normalize_configuration_payload(data, warn_legacy=False)
        return data
    kind = _legacy_workflow_kind(data, expected_kind=None)
    _normalize_legacy_aliases(data, kind)
    return _legacy_to_canonical(data, kind)


def rebase_migrated_configuration_paths(
    payload: Mapping[str, Any],
    *,
    legacy_base: str | Path,
    schema_base: str | Path,
) -> dict[str, Any]:
    """Preserve legacy path targets after migration to schema 2.

    Legacy files inside a source checkout resolve relative paths from the
    checkout root, whereas schema-2 files resolve them beside their YAML file.
    This function rewrites only the documented path fields so both mappings
    still designate the same files and directories.
    """
    data = copy.deepcopy(dict(payload))
    kind = configuration_workflow_kind(data)
    if kind == "single_date":
        source_data = _canonical_section(data, "data")
        source_data.setdefault("data_dir", "examples/data")
        lpm = _canonical_section(data, "lpm")
        lpm.setdefault("directory", "data_core/data_lpm")
        fields = (
            (source_data, "data_dir"),
            (lpm, "directory"),
            (_optional_canonical_section(data, "tracers"), "data_directory"),
            (_optional_canonical_section(data, "output"), "directory"),
        )
    else:
        fields = (
            (_optional_canonical_section(data, "data"), "file"),
            (_optional_canonical_section(data, "lpm"), "directory"),
            (_optional_canonical_section(data, "output"), "directory"),
        )
    for section, field in fields:
        if section is not None and field in section:
            section[field] = _rebase_path_value(
                section[field],
                legacy_base=Path(legacy_base),
                schema_base=Path(schema_base),
            )
    return data


def _canonical_section(data: dict[str, Any], name: str) -> dict[str, Any]:
    """Return one canonical mapping section, creating it when absent."""
    section = data.setdefault(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"{name} must be a mapping")
    return section


def _optional_canonical_section(
    data: dict[str, Any], name: str
) -> dict[str, Any] | None:
    """Return one optional canonical mapping section without creating it."""
    section = data.get(name)
    if section is None:
        return None
    if not isinstance(section, dict):
        raise ValueError(f"{name} must be a mapping")
    return section


def _rebase_path_value(
    value: object,
    *,
    legacy_base: Path,
    schema_base: Path,
) -> object:
    """Rebase one relative path while leaving invalid values to validation."""
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    target = (legacy_base.resolve() / path).resolve()
    try:
        relative = Path(os.path.relpath(target, schema_base.resolve()))
    except ValueError:
        # Different Windows drives cannot be represented by one relative path.
        return str(target)
    return relative.as_posix()


def _mapping_section(
    data: dict[str, Any],
    name: str,
    *,
    required: bool = False,
) -> dict[str, Any] | None:
    """Pop an optional mapping section and reject ambiguous scalar values."""
    if name not in data:
        if required:
            raise ValueError(f"{name} must be a mapping")
        return None
    value = data.pop(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return copy.deepcopy(dict(value))


def _legacy_workflow_kind(
    data: dict[str, Any], expected_kind: WorkflowKind | None
) -> WorkflowKind:
    """Resolve a legacy kind, restoring the pre-discriminator default."""
    workflow = data.get("workflow")
    if workflow is None:
        kind = expected_kind or "single_date"
        data["workflow"] = {"kind": kind}
        return kind
    kind = configuration_workflow_kind(data)
    if expected_kind is not None and kind != expected_kind:
        raise ValueError(f"Expected a {expected_kind} configuration, received {kind}")
    return kind


def _normalize_legacy_aliases(data: dict[str, Any], kind: WorkflowKind) -> None:
    """Keep published 1.x field spellings accepted by workflow loaders."""
    if kind != "temporal":
        return
    lpm_models = data.get("lpm_models")
    if not isinstance(lpm_models, dict) or "list" not in lpm_models:
        return
    if "models" in lpm_models:
        raise ValueError("lpm_models.list and lpm_models.models cannot be combined")
    lpm_models["models"] = lpm_models.pop("list")


def _reject_keys(section: Mapping[str, Any], keys: set[str], label: str) -> None:
    present = sorted(keys.intersection(section))
    if present:
        raise ValueError(
            f"Schema 2 {label} uses canonical field names; legacy fields are "
            f"not allowed here: {present}"
        )


def _canonical_mh_to_runtime(
    section: dict[str, Any], kind: WorkflowKind
) -> dict[str, Any]:
    """Translate shared schema-2 MH controls to one runtime model."""
    _reject_keys(section, {"nstep", "mh_nsteps", "nskip", "seed_enabled"}, "MH")
    renamed: dict[str, Any] = {}
    for name, value in section.items():
        if name == "nsteps":
            renamed["nstep" if kind == "single_date" else "mh_nsteps"] = value
        elif name == "thinning":
            renamed["nskip"] = value
        else:
            renamed[name] = value
    if kind == "temporal" and "seed" in renamed:
        seed = renamed["seed"]
        renamed["seed_enabled"] = seed is not None
        if seed is None:
            renamed.pop("seed")
    return renamed


def _canonical_lpm_to_runtime(
    section: dict[str, Any], kind: WorkflowKind
) -> tuple[str, dict[str, Any]]:
    """Translate the common LPM selector to its workflow runtime section."""
    _reject_keys(section, {"model_name", "data_directory"}, "lpm")
    allowed = {"models", "directory"}
    unknown = sorted(set(section) - allowed)
    if unknown:
        raise ValueError(f"Unknown schema 2 lpm fields: {unknown}")
    models = section.get("models")
    directory = section.get("directory")
    if kind == "single_date":
        runtime: dict[str, Any] = {"data_directory": str(DIRECTORY_LPM_DATA)}
        if models is not None:
            if not isinstance(models, list) or len(models) != 1:
                raise ValueError(
                    "single_date schema 2 lpm.models must contain exactly one model"
                )
            runtime["model_name"] = models[0]
        if directory is not None:
            runtime["data_directory"] = directory
        return "lpm", runtime
    runtime = {}
    if models is not None:
        runtime["models"] = models
    if directory is not None:
        runtime["directory"] = directory
    return "lpm_models", runtime


def _canonical_to_runtime(data: dict[str, Any], kind: WorkflowKind) -> dict[str, Any]:
    """Translate a schema-2 mapping into an existing strict runtime schema."""
    legacy_top_level = {
        "dataset",
        "results",
        "lpm_models",
        "calibration_metropolis_hastings",
        "calibration_simplex",
        "figures",
    }
    present = sorted(legacy_top_level.intersection(data))
    if present:
        raise ValueError(
            f"Schema 2 configuration contains legacy top-level sections: {present}"
        )

    runtime = data
    source_data = _mapping_section(runtime, "data")
    if source_data is not None:
        runtime["dataset"] = source_data

    lpm = _mapping_section(runtime, "lpm")
    if lpm is not None:
        name, section = _canonical_lpm_to_runtime(lpm, kind)
        runtime[name] = section

    _move_canonical_calibration(runtime, kind)
    _move_canonical_output_sections(runtime, kind)
    return runtime


def _move_canonical_calibration(runtime: dict[str, Any], kind: WorkflowKind) -> None:
    """Move shared calibration sections to the selected runtime schema."""
    calibration = _mapping_section(runtime, "calibration")
    if calibration is None:
        return
    mh = _mapping_section(calibration, "metropolis_hastings")
    simplex = _mapping_section(calibration, "simplex")
    if calibration:
        raise ValueError(
            f"Unknown schema 2 calibration sections: {sorted(calibration)}"
        )
    if mh is not None:
        runtime_name = (
            "calibration_metropolis_hastings"
            if kind == "single_date"
            else "calibration"
        )
        runtime[runtime_name] = _canonical_mh_to_runtime(mh, kind)
    if simplex is not None:
        if kind != "single_date":
            raise ValueError(
                "calibration.simplex is available only for single_date workflows"
            )
        runtime["calibration_simplex"] = simplex


def _move_canonical_output_sections(
    runtime: dict[str, Any], kind: WorkflowKind
) -> None:
    """Move shared reporting and output sections to runtime names."""
    reporting = _mapping_section(runtime, "reporting")
    if reporting is not None:
        if kind != "temporal":
            raise ValueError("reporting is available only for temporal workflows")
        runtime["figures"] = reporting

    output = _mapping_section(runtime, "output")
    if output is not None:
        runtime["results"] = output


def _legacy_mh_to_canonical(
    section: dict[str, Any], kind: WorkflowKind
) -> dict[str, Any]:
    """Rename legacy MH schedule fields without changing their values."""
    result: dict[str, Any] = {}
    step_name = "nstep" if kind == "single_date" else "mh_nsteps"
    for name, value in section.items():
        if name == step_name:
            result["nsteps"] = value
        elif name == "nskip":
            result["thinning"] = value
        elif kind == "temporal" and name == "seed_enabled":
            continue
        elif kind == "temporal" and name == "seed":
            if section.get("seed_enabled"):
                result["seed"] = value
        else:
            result[name] = value
    return result


def _legacy_lpm_to_canonical(
    section: dict[str, Any], kind: WorkflowKind
) -> dict[str, Any]:
    """Convert one legacy workflow LPM selector to the common section."""
    result: dict[str, Any] = {}
    if kind == "single_date":
        if "model_name" in section:
            result["models"] = [section.pop("model_name")]
        if "data_directory" in section:
            result["directory"] = section.pop("data_directory")
    else:
        if "models" in section:
            result["models"] = section.pop("models")
        if "directory" in section:
            result["directory"] = section.pop("directory")
    result.update(section)
    return result


def _legacy_to_canonical(data: dict[str, Any], kind: WorkflowKind) -> dict[str, Any]:
    """Convert an unversioned 1.x mapping to the schema-2 section layout."""
    canonical: dict[str, Any] = {
        "schema_version": CONFIGURATION_SCHEMA_VERSION,
    }
    if "workflow" in data:
        canonical["workflow"] = data.pop("workflow")
    if "dataset" in data:
        canonical["data"] = data.pop("dataset")

    lpm_name = "lpm" if kind == "single_date" else "lpm_models"
    lpm = _mapping_section(data, lpm_name)
    if lpm is not None:
        canonical["lpm"] = _legacy_lpm_to_canonical(lpm, kind)

    calibration: dict[str, Any] = {}
    mh_name = (
        "calibration_metropolis_hastings" if kind == "single_date" else "calibration"
    )
    mh = _mapping_section(data, mh_name)
    if mh is not None:
        calibration["metropolis_hastings"] = _legacy_mh_to_canonical(mh, kind)
    if kind == "single_date":
        simplex = _mapping_section(data, "calibration_simplex")
        if simplex is not None:
            calibration["simplex"] = simplex
    if calibration:
        canonical["calibration"] = calibration

    if kind == "temporal" and "figures" in data:
        canonical["reporting"] = data.pop("figures")
    if "results" in data:
        canonical["output"] = data.pop("results")
    canonical.update(data)
    return canonical


__all__ = [
    "CONFIGURATION_SCHEMA_VERSION",
    "LegacyConfigurationWarning",
    "WorkflowKind",
    "configuration_base_directory",
    "configuration_workflow_kind",
    "is_legacy_configuration",
    "migrate_configuration_payload",
    "normalize_configuration_payload",
    "rebase_migrated_configuration_paths",
]
