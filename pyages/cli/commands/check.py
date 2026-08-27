# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Verify the PyAges installation and its core resources."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module

import click
from pydantic import ValidationError

from pyages.config.models import CliCheckParams


@dataclass(frozen=True)
class CheckResult:
    """Number of successful and failed checks."""

    passed: int = 0
    failed: int = 0


def _ok(message: str) -> None:
    click.echo(click.style("[OK]", fg="green") + f" {message}")


def _fail(message: str) -> None:
    click.echo(click.style("[FAIL]", fg="red") + f" {message}")


def _check_python() -> CheckResult:
    version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    if sys.version_info >= (3, 12):
        _ok(f"Python version: {version}")
        return CheckResult(passed=1)
    _fail(f"Python version: {version} (requires >= 3.12)")
    return CheckResult(failed=1)


def _check_dependencies(verbose: bool) -> CheckResult:
    dependencies = [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("pandas", "pandas"),
        ("matplotlib", "matplotlib"),
        ("yaml", "pyyaml"),
        ("click", "click"),
    ]
    passed = 0
    failed = 0
    for module_name, package_name in dependencies:
        try:
            module = import_module(module_name)
        except ImportError:
            _fail(f"{package_name} not installed")
            failed += 1
            continue
        passed += 1
        if verbose:
            _ok(f"{package_name}: {getattr(module, '__version__', '?')}")
    if not verbose and failed == 0:
        _ok(f"Dependencies: {passed} packages found")
    return CheckResult(passed=passed, failed=failed)


def _check_lpm_registry(verbose: bool) -> CheckResult:
    try:
        from pyages.lpm.factory import list_available_lpms

        models = list_available_lpms()
    except Exception as exc:
        _fail(f"LPM registry: {exc}")
        return CheckResult(failed=1)
    _ok(f"LPM registry: {len(models)} models")
    if verbose:
        for model in models:
            click.echo(f"       - {model}")
    return CheckResult(passed=1)


def _check_tracers(verbose: bool) -> CheckResult:
    try:
        from pyages.config.paths import DIRECTORY_TRACER_DATA

        names = sorted(
            path.name
            for path in DIRECTORY_TRACER_DATA.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        )
    except Exception as exc:
        _fail(f"Tracer data: {exc}")
        return CheckResult(failed=1)
    _ok(f"Tracers: {len(names)} found")
    if verbose:
        click.echo(f"       Location: {DIRECTORY_TRACER_DATA}")
        for name in names:
            click.echo(f"       - {name}")
    return CheckResult(passed=1)


def _check_paths(verbose: bool) -> CheckResult:
    try:
        from pyages.config.paths import (
            DIRECTORY_LPM_DATA,
            DIRECTORY_TRACER_DATA,
            ROOT_DIRECTORY_RESULTS,
        )
    except Exception as exc:
        _fail(f"Path config: {exc}")
        return CheckResult(failed=1)
    if verbose:
        _ok(f"Results dir: {ROOT_DIRECTORY_RESULTS}")
        _ok(f"LPM data: {DIRECTORY_LPM_DATA}")
        _ok(f"Tracer data: {DIRECTORY_TRACER_DATA}")
    else:
        _ok("Data directories configured")
    return CheckResult(passed=1)


def _run_checks(verbose: bool) -> CheckResult:
    results = [
        _check_python(),
        _check_dependencies(verbose),
        _check_lpm_registry(verbose),
        _check_tracers(verbose),
        _check_paths(verbose),
    ]
    return CheckResult(
        passed=sum(result.passed for result in results),
        failed=sum(result.failed for result in results),
    )


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed check results")
def check(verbose: bool) -> None:
    """Check PyAges installation and system health.

    \b
    Verifies:
      - Python version >= 3.12
      - Required dependencies are installed
      - LPM models can be loaded
      - Tracers can be discovered
    """
    try:
        params = CliCheckParams.model_validate({"verbose": verbose})
    except ValidationError as exc:
        raise click.ClickException(f"Invalid CLI arguments:\n{exc}") from exc

    click.echo("PyAges Installation Check")
    click.echo("=" * 40)
    result = _run_checks(params.verbose)

    click.echo()
    click.echo("=" * 40)
    total = result.passed + result.failed
    if result.failed == 0:
        message = click.style(f"All {total} checks passed.", fg="green", bold=True)
        click.echo(f"{message} PyAges is ready!")
        return
    click.echo(
        click.style(
            f"{result.failed}/{total} checks failed.",
            fg="red",
            bold=True,
        )
    )
    raise click.exceptions.Exit(1)
