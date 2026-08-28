# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Run the documented PyAges pytest scopes from the repository root.

Examples:
  python run_tests.py standard
  python run_tests.py standard detail
  python run_tests.py extensive
  python run_tests.py coverage
  python run_tests.py validation
  python run_tests.py collect
  python run_tests.py standard update
"""

import argparse
import subprocess
import sys
from collections.abc import Sequence

PRIMARY_SCOPES = {"standard", "extensive", "coverage", "validation", "collect"}
MODIFIERS = {"detail", "update"}
VALID_MODES = PRIMARY_SCOPES | MODIFIERS
TRACERLPM_TESTS = "validation/tracerlpm/benchmark/tests"


def build_pytest_command(modes: Sequence[str]) -> list[str]:
    """Return the pytest command for a validated collection of modes."""
    requested = set(modes)
    unknown = requested - VALID_MODES
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown mode(s): {names}")

    scopes = requested & PRIMARY_SCOPES
    if not scopes:
        raise ValueError("choose exactly one test scope")
    if len(scopes) > 1:
        names = ", ".join(sorted(scopes))
        raise ValueError(f"choose exactly one test scope, not: {names}")
    scope = next(iter(scopes))

    if "update" in requested and scope not in {"standard", "extensive"}:
        raise ValueError("update is supported only for standard or extensive tests")

    verbosity = "-vv" if "detail" in requested else "-q"
    command = [sys.executable, "-m", "pytest"]

    if scope == "collect":
        command.extend(["--collect-only", verbosity, "tests"])
    elif scope == "validation":
        command.extend([verbosity, TRACERLPM_TESTS])
    elif scope == "coverage":
        command.extend(
            [
                verbosity,
                "tests",
                "--cov=pyages",
                "--cov-branch",
                "--cov-report=term-missing",
                "--cov-report=xml",
                "--cov-fail-under=75",
            ]
        )
    else:
        command.extend([verbosity, "tests"])
        if scope == "extensive":
            command.append("--run-extensive")

    if "update" in requested:
        command.extend(["-s", "--update-golden"])

    return command


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a documented PyAges pytest scope."
    )
    parser.add_argument(
        "modes",
        nargs="*",
        choices=sorted(VALID_MODES),
        metavar="MODE",
        help=(
            "one scope (standard, extensive, coverage, validation, collect) "
            "plus optional detail or update"
        ),
    )
    args = parser.parse_args(argv)

    try:
        command = build_pytest_command(args.modes)
    except ValueError as error:
        parser.error(str(error))

    print("Running:", " ".join(command))
    print("-" * 60)
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
