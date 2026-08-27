# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Verify the PyAges installation and its core resources."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import metadata

import click
from packaging.requirements import InvalidRequirement, Requirement
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


def _python_version_supported(version_info: tuple[int, int, int]) -> bool:
    return (3, 12) <= version_info < (3, 15)


def _check_python() -> CheckResult:
    version_info = sys.version_info[:3]
    version = ".".join(str(part) for part in version_info)
    if _python_version_supported(version_info):
        _ok(f"Python version: {version}")
        return CheckResult(passed=1)
    _fail(f"Python version: {version} (requires >= 3.12,<3.15)")
    return CheckResult(failed=1)


def _active_runtime_requirements() -> list[Requirement]:
    """Return the installed distribution's active non-extra requirements."""

    try:
        declared = metadata.requires("pyages")
    except metadata.PackageNotFoundError:
        return []

    requirements = []
    for raw_requirement in declared or []:
        try:
            requirement = Requirement(raw_requirement)
        except InvalidRequirement:
            continue
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            requirements.append(requirement)
    return requirements


def _check_dependencies(verbose: bool) -> CheckResult:
    dependencies = _active_runtime_requirements()
    if not dependencies:
        _fail("Distribution metadata unavailable; install PyAges with pip")
        return CheckResult(failed=1)

    passed = 0
    failed = 0
    for requirement in dependencies:
        try:
            installed_version = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            _fail(
                f"{requirement.name} not installed (requires {requirement.specifier})"
            )
            failed += 1
            continue

        if installed_version not in requirement.specifier:
            _fail(
                f"{requirement.name}: {installed_version} does not satisfy "
                f"{requirement.specifier}"
            )
            failed += 1
            continue

        passed += 1
        if verbose:
            _ok(f"{requirement.name}: {installed_version}")
    if not verbose and failed == 0:
        _ok(f"Dependencies: {passed} version constraints satisfied")
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
      - Python version >= 3.12,<3.15
      - Required dependency versions satisfy package metadata
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
