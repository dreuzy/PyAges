# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

import tomllib
from pathlib import Path

from scripts.check_project_metadata import (
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
