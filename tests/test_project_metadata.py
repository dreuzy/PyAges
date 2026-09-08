# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path

from scripts.maintenance import check_project_metadata
from scripts.maintenance.check_project_metadata import (
    canonical_naming_errors,
    dependency_alignment_errors,
    installed_dependency_errors,
    release_identity_errors,
)

ROOT = Path(__file__).resolve().parents[1]


def test_qualified_runtime_dependencies_are_compatible():
    assert dependency_alignment_errors() == []


def _qualified_installed_version(name: str) -> str:
    normalized = check_project_metadata._normalized_name(name)
    versions = {
        **check_project_metadata._qualified_pip_versions(),
        **check_project_metadata._qualified_bootstrap_versions(),
    }
    return versions[normalized]


def test_installed_dependency_check_covers_requested_extras(monkeypatch):
    requested: list[str] = []

    def fake_version(name: str) -> str:
        requested.append(check_project_metadata._normalized_name(name))
        return _qualified_installed_version(name)

    monkeypatch.setattr(
        check_project_metadata.importlib.metadata, "version", fake_version
    )

    assert installed_dependency_errors(("dev", "docs", "examples")) == []
    assert {"ruff", "sphinx", "jupyterlab"} <= set(requested)


def test_installed_dependency_check_reports_missing_package(monkeypatch):
    def fake_version(name: str) -> str:
        if check_project_metadata._normalized_name(name) == "ruff":
            raise PackageNotFoundError(name)
        return _qualified_installed_version(name)

    monkeypatch.setattr(
        check_project_metadata.importlib.metadata, "version", fake_version
    )

    assert "installed dev dependency is missing: ruff" in installed_dependency_errors(
        ("dev",)
    )


def test_qualified_check_distinguishes_compatible_from_exact(monkeypatch):
    def fake_version(name: str) -> str:
        if check_project_metadata._normalized_name(name) == "click":
            return "8.4.2"
        return _qualified_installed_version(name)

    monkeypatch.setattr(
        check_project_metadata.importlib.metadata, "version", fake_version
    )

    assert installed_dependency_errors() == []
    errors = installed_dependency_errors(require_qualified_versions=True)
    assert errors == [
        "installed runtime dependency does not match the qualified pin: "
        "click==8.4.2, expected 8.5.0"
    ]


def test_public_project_identity_is_canonically_pyages():
    assert canonical_naming_errors() == []


def test_pandas_future_string_ci_installs_its_required_backend():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pandas_job = workflow.split("  pandas-compatibility:", maxsplit=1)[1].split(
        "\n  coverage:", maxsplit=1
    )[0]

    assert '"pandas==2.2.3"' in pandas_job
    assert '"pyarrow>=10.0.1"' in pandas_job
    assert "pd.options.future.infer_string = True" in pandas_job


def test_scheduled_dependency_audit_checks_exact_pins_and_freshness():
    workflow = (ROOT / ".github" / "workflows" / "dependency-audit.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "23 4 * * 2"' in workflow
    assert "install/bootstrap-constraints.txt" in workflow
    assert "--extra dev --extra docs --extra examples" in workflow
    assert "--require-qualified-versions" in workflow
    assert "python -m pip check" in workflow
    assert "python -m pip_audit --local --skip-editable" in workflow
    assert "python -m pip list --outdated" in workflow


def test_dependabot_groups_dependency_updates_by_qualification_scope():
    configuration = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert "scientific-runtime:" in configuration
    assert "developer-tooling:" in configuration
    assert "documentation:" in configuration
    assert "bootstrap-packaging:" in configuration
    assert "- setuptools" in configuration


def test_release_identity_is_aligned():
    assert release_identity_errors("1.2.0") == []
    assert release_identity_errors("v1.2.0") == [
        "tag/version mismatch: tag=v1.2.0, package=1.2.0"
    ]


def test_package_publish_workflow_uses_isolated_trusted_publishing_jobs():
    workflow = (ROOT / ".github" / "workflows" / "publish-package.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert workflow.count("id-token: write") == 2
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert (
        workflow.count(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
        )
        == 2
    )
    assert "python -m build" not in workflow
    assert 'gh release download "$RELEASE_TAG"' in workflow
    assert "packaging PyYAML twine" in workflow


def test_data_core_separates_runtime_resources_from_sources():
    data_core = ROOT / "data_core"
    source_workbooks = sorted((data_core / "sources" / "tracer").glob("*.xlsx"))

    assert (data_core / "README.md").is_file()
    assert len(source_workbooks) == 3
    assert not list((data_core / "data_tracer").glob("*.xlsx"))

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = set(project["tool"]["setuptools"]["package-data"]["data_core"])
    assert "README.md" in packaged
    assert not any(path.startswith("sources/") for path in packaged)

    source_manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "prune data_core/sources" in source_manifest
    assert "include install/bootstrap-constraints.txt" in source_manifest


def test_repository_scripts_are_grouped_by_responsibility():
    scripts = ROOT / "scripts"
    expected_modules = {
        "common": {
            "example_case_utils.py",
            "example_single_date_utils.py",
            "provenance.py",
            "publication_plotting.py",
            "reporting.py",
            "structured_data.py",
        },
        "article": {
            "audit_ploemeur_article_nonregression.py",
            "build_article_non_ploemeur_report.py",
            "build_final_scientific_audit.py",
            "postprocess_existing.py",
            "postprocess_holten_prior_sensitivity.py",
            "postprocess_shifted_exponential_mtt_uncertainty.py",
            "reproduce_article.py",
            "reproduce_manuscript_figure2.py",
            "run_article_non_ploemeur.py",
            "run_case.py",
            "run_final_holten_h4.py",
            "run_final_shifted_exponential.py",
            "run_full.py",
            "run_holten_prior_robustness.py",
            "run_ploemeur_shifted_exponential_final.py",
            "run_ploemeur_targeted_ig_reproduction.py",
            "run_remaining_non_ploemeur_simulations.py",
            "run_tracerlpm_article_campaign.py",
            "update_manuscript_figures.py",
            "verify_forward.py",
        },
        "qualification": {
            "_archive_contract.py",
            "_archive_evidence.py",
            "_archive_verification.py",
            "build_ci_multichain_archive.py",
            "build_multichain_archive.py",
            "qualify_mh_proposals.py",
            "run_calibration_benchmark.py",
            "run_system_check.py",
        },
        "release": {
            "build_article_package.py",
            "build_reproduction_archive.py",
            "build_zenodo_bundle.py",
            "promote_article_campaign.py",
        },
        "maintenance": {
            "benchmark_model_space.py",
            "check_architecture.py",
            "check_dev.py",
            "check_licensing.py",
            "check_project_metadata.py",
            "check_qualified_docstrings.py",
            "clean_release_artifacts.py",
            "generate_test_inventory.py",
        },
    }

    assert {path.name for path in scripts.glob("*.py")} == {"__init__.py"}
    for family, expected in expected_modules.items():
        actual = {
            path.name
            for path in (scripts / family).glob("*.py")
            if path.name != "__init__.py"
        }
        assert actual == expected

    assert not list((ROOT / "article").rglob("*.py"))


def test_script_tests_mirror_entrypoint_families():
    tests = ROOT / "tests" / "scripts"
    expected_tests = {
        "common": {"test_structured_data.py"},
        "article": {
            "test_article_campaign.py",
            "test_article_support.py",
            "test_holten_prior_robustness.py",
            "test_ploemeur_shifted_exponential_final.py",
            "test_ploemeur_targeted_ig_reproduction.py",
            "test_publication_figures.py",
            "test_remaining_non_ploemeur_simulations.py",
            "test_reproduce_manuscript_figure2.py",
        },
        "qualification": {
            "test_ci_multichain_archive.py",
            "test_multichain_archive.py",
            "test_qualify_mh_proposals.py",
            "test_run_calibration_benchmark.py",
        },
        "release": {"test_campaign_promotion.py", "test_zenodo_bundle.py"},
        "maintenance": {
            "test_benchmark_model_space.py",
            "test_check_architecture.py",
            "test_check_dev.py",
            "test_generate_test_inventory.py",
            "test_run_tests.py",
        },
    }

    assert not list(tests.glob("test_*.py"))
    for family, expected in expected_tests.items():
        assert {path.name for path in (tests / family).glob("test_*.py")} == expected
