# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for package metadata and the intentionally small root API."""

import re
from pathlib import Path

import yaml
from click.testing import CliRunner

import pyages
import pyages.qualification as qualification
import pyages.workflows.runtime as workflow_runtime
from pyages.calibration.methods import mh
from pyages.calibration.methods.mh import config as mh_config
from pyages.calibration.methods.mh import ensemble as mh_ensemble
from pyages.calibration.methods.mh import ensemble_config as mh_ensemble_config
from pyages.calibration.methods.mh import errors as mh_errors
from pyages.calibration.methods.mh import results as mh_results
from pyages.calibration.methods.mh import sampler as mh_sampler
from pyages.cli.main import cli
from pyages.workflows.runtime import manifest as runtime_manifest
from pyages.workflows.runtime import mh as runtime_mh

ROOT = Path(__file__).resolve().parents[1]


def test_package_exposes_version() -> None:
    assert re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?", pyages.__version__)
    assert pyages.__all__ == ["__version__"]


def test_cli_uses_package_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"pyages, version {pyages.__version__}"


def test_citation_uses_package_version() -> None:
    """Keep the citable release identity synchronized with runtime metadata."""
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    assert citation["type"] == "software"
    assert citation["version"] == pyages.__version__
    release_date = citation["date-released"].isoformat()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"## {pyages.__version__} - {release_date}" in changelog
    assert f"`{pyages.__version__}`" in readme
    for identifier in citation.get("identifiers", []):
        if identifier.get("type") == "doi":
            assert re.fullmatch(r"10\.\d{4,9}/\S+", identifier["value"])
            assert not re.search(r"TBD|TODO|PLACEHOLDER", identifier["value"], re.I)


def test_removed_compatibility_facades_are_absent() -> None:
    removed_paths = (
        "pyages/qualification/__init__.py",
        "pyages/qualification/synthetic_recovery.py",
        "pyages/workflows/concentration_exports.py",
        "pyages/workflows/plotting_runtime.py",
        "pyages/workflows/plots/__init__.py",
        "pyages/workflows/result_manifest.py",
        "pyages/workflows/single_date_config.py",
        "pyages/workflows/single_date_paths.py",
        "pyages/workflows/synthetic_recovery.py",
    )

    assert all(not (ROOT / path).exists() for path in removed_paths)


def test_qualification_exposes_the_experiment_without_a_workflow_alias() -> None:
    assert qualification.__all__ == ["SyntheticRecoveryExperiment"]
    assert not hasattr(qualification, "SyntheticRecoveryWorkflow")


def test_mh_facade_exports_only_canonical_objects() -> None:
    expected = {
        "MHChainResult": mh_results.MHChainResult,
        "MHConfig": mh_config.MHConfig,
        "MHConvergenceError": mh_errors.MHConvergenceError,
        "MHDiagnosticsConfig": mh_ensemble_config.MHDiagnosticsConfig,
        "MHDiagnosticsUnavailableError": mh_errors.MHDiagnosticsUnavailableError,
        "MHEnsembleConfig": mh_ensemble_config.MHEnsembleConfig,
        "MHInitializationConfig": mh_ensemble_config.MHInitializationConfig,
        "MHParameterDiagnostics": mh_results.MHParameterDiagnostics,
        "MHPilotConfig": mh_ensemble_config.MHPilotConfig,
        "MHPilotResult": mh_results.MHPilotResult,
        "MHRunRecord": mh_results.MHRunRecord,
        "MHSeedPlan": mh_ensemble_config.MHSeedPlan,
        "MetropolisHastings": mh_sampler.MetropolisHastings,
        "MultiChainMetropolisHastings": (mh_ensemble.MultiChainMetropolisHastings),
        "build_seed_plan": mh_ensemble_config.build_seed_plan,
    }

    assert mh.__all__ == list(expected)
    assert all(getattr(mh, name) is value for name, value in expected.items())
    assert not hasattr(mh, "MHEnsembleResult")
    assert not hasattr(mh_ensemble, "ProblemFactory")
    assert not hasattr(runtime_mh, "build_mh_ensemble_config")
    assert not hasattr(runtime_mh, "mh_stage_directory")


def test_workflow_runtime_facade_exports_only_canonical_lifecycle_services() -> None:
    expected = {
        "ResultRun": runtime_manifest.ResultRun,
        "begin_staged_result_run": runtime_manifest.begin_staged_result_run,
        "promote_result_run": runtime_manifest.promote_result_run,
        "write_failure_manifest": runtime_manifest.write_failure_manifest,
        "write_result_manifest": runtime_manifest.write_result_manifest,
    }

    assert workflow_runtime.__all__ == list(expected)
    assert all(
        getattr(workflow_runtime, name) is value for name, value in expected.items()
    )
    assert not hasattr(workflow_runtime, "RESULT_SCHEMA_VERSION")
    assert not hasattr(workflow_runtime, "begin_result_run")
    assert not hasattr(workflow_runtime, "_promotion_lock")


def test_manifest_exports_stage_operations_outside_the_contributor_facade() -> None:
    operational_names = {
        "StagedRunInspection",
        "inspect_staged_result_run",
        "inventory_staged_result_runs",
        "quarantine_staged_result_run",
    }

    assert operational_names <= set(runtime_manifest.__all__)
    assert all(hasattr(runtime_manifest, name) for name in operational_names)
    assert all(not hasattr(workflow_runtime, name) for name in operational_names)
    assert "promotable_now" in runtime_manifest.StagedRunInspection.__annotations__
    assert "promotable" not in runtime_manifest.StagedRunInspection.__annotations__
