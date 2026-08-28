# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import tomllib
from pathlib import Path

from scripts.maintenance.check_project_metadata import (
    dependency_alignment_errors,
    release_identity_errors,
)

ROOT = Path(__file__).resolve().parents[1]


def test_qualified_runtime_dependencies_are_compatible():
    assert dependency_alignment_errors() == []


def test_release_identity_is_aligned():
    assert release_identity_errors("1.0") == []
    assert release_identity_errors("v1.0") == [
        "tag/version mismatch: tag=v1.0, package=1.0"
    ]


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


def test_repository_scripts_are_grouped_by_responsibility():
    scripts = ROOT / "scripts"
    expected_modules = {
        "article": {
            "audit_ploemeur_article_nonregression.py",
            "build_article_non_ploemeur_report.py",
            "build_final_scientific_audit.py",
            "postprocess_existing.py",
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
            "qualify_mh_proposals.py",
            "run_calibration_benchmark.py",
            "run_system_check.py",
        },
        "release": {
            "build_article_package.py",
            "build_reproduction_archive.py",
            "build_zenodo_bundle.py",
        },
        "maintenance": {
            "check_licensing.py",
            "check_project_metadata.py",
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
        "qualification": {"test_qualify_mh_proposals.py"},
        "release": {"test_zenodo_bundle.py"},
        "maintenance": {
            "test_generate_test_inventory.py",
            "test_run_tests.py",
        },
    }

    assert not list(tests.glob("test_*.py"))
    for family, expected in expected_tests.items():
        assert {path.name for path in (tests / family).glob("test_*.py")} == expected
