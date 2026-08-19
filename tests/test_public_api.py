"""Contracts for package metadata and the intentionally small root API."""

import re

from click.testing import CliRunner

import pyage
from pyage.cli.main import cli


def test_package_exposes_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?", pyage.__version__)
    assert pyage.__all__ == ["__version__"]


def test_cli_uses_package_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"pyage, version {pyage.__version__}"
