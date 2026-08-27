# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Contracts for package metadata and the intentionally small root API."""

import re
from pathlib import Path

import yaml
from click.testing import CliRunner

import pyages
from pyages.cli.main import cli

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
