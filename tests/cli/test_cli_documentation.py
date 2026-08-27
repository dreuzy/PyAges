"""Keep the hand-written CLI reference synchronized with Click help."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from pyage.cli.main import cli

ROOT = Path(__file__).resolve().parents[2]
CLI_REFERENCE = ROOT / "docs" / "user-guide" / "cli-flags.md"


@pytest.mark.parametrize(
    "command",
    [
        [],
        ["check"],
        ["list"],
        ["list", "lpms"],
        ["list", "tracers"],
        ["run"],
        ["new"],
        ["new", "lpm"],
        ["new", "tracer"],
    ],
)
def test_every_long_cli_option_is_documented(command: list[str]) -> None:
    result = CliRunner().invoke(cli, [*command, "--help"])
    assert result.exit_code == 0
    options = set(re.findall(r"(?<!\w)--[a-z][a-z0-9-]*", result.output))
    options.discard("--help")
    documentation = CLI_REFERENCE.read_text(encoding="utf-8")

    missing = sorted(option for option in options if option not in documentation)
    command_name = " ".join(command) or "pyage"
    assert not missing, f"Undocumented options for {command_name}: {missing}"
