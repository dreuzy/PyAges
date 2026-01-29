"""
PyAge check command - Verify installation and system health.
"""

import sys

import click
from pydantic import ValidationError

from pyage.config.models import CliCheckParams


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed check results")
def check(verbose: bool):
    """Check PyAge installation and system health.

    \b
    Verifies:
      - Python version >= 3.9
      - Required dependencies are installed
      - LPM models can be loaded
      - Tracers can be discovered

    \b
    Example:
        pyage check
        pyage check --verbose
    """
    try:
        params = CliCheckParams.model_validate({"verbose": verbose})
    except ValidationError as exc:
        click.echo(click.style(f"Invalid CLI arguments:\n{exc}", fg="red"))
        sys.exit(1)

    verbose = params.verbose

    click.echo("PyAge Installation Check")
    click.echo("=" * 40)

    checks_passed = 0
    checks_failed = 0

    # Check 1: Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 9):
        click.echo(click.style("[OK]", fg="green") + f" Python version: {py_version}")
        checks_passed += 1
    else:
        click.echo(
            click.style("[FAIL]", fg="red")
            + f" Python version: {py_version} (requires >= 3.9)"
        )
        checks_failed += 1

    # Check 2: Core dependencies
    deps = [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("pandas", "pandas"),
        ("matplotlib", "matplotlib"),
        ("yaml", "pyyaml"),
        ("click", "click"),
    ]

    for module_name, package_name in deps:
        try:
            mod = __import__(module_name)
            version = getattr(mod, "__version__", "?")
            if verbose:
                click.echo(
                    click.style("[OK]", fg="green") + f" {package_name}: {version}"
                )
            checks_passed += 1
        except ImportError:
            click.echo(
                click.style("[FAIL]", fg="red") + f" {package_name} not installed"
            )
            checks_failed += 1

    if not verbose:
        click.echo(
            click.style("[OK]", fg="green")
            + f" Dependencies: {len(deps)} packages found"
        )

    # Check 3: LPM registry
    try:
        from pyage.LPM.lpm_build import list_available_lpms

        lpms = list_available_lpms()
        click.echo(
            click.style("[OK]", fg="green") + f" LPM registry: {len(lpms)} models"
        )
        if verbose:
            for lpm in lpms:
                click.echo(f"       - {lpm}")
        checks_passed += 1
    except Exception as e:
        click.echo(click.style("[FAIL]", fg="red") + f" LPM registry: {e}")
        checks_failed += 1

    # Check 4: Tracer directory
    try:
        from pyage.tracer.tracer_root import find_tracer_dir

        tracer_dir = find_tracer_dir()
        tracer_names = sorted(
            [
                d.name
                for d in tracer_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
        )
        click.echo(
            click.style("[OK]", fg="green") + f" Tracers: {len(tracer_names)} found"
        )
        if verbose:
            click.echo(f"       Location: {tracer_dir}")
            for name in tracer_names:
                click.echo(f"       - {name}")
        checks_passed += 1
    except Exception as e:
        click.echo(click.style("[FAIL]", fg="red") + f" Tracer data: {e}")
        checks_failed += 1

    # Check 5: Data directories
    try:
        from pyage.config.paths import (
            DIRECTORY_LPM_DATA,
            DIRECTORY_TRACER_DATA,
            ROOT_DIRECTORY_RESULTS,
        )

        if verbose:
            click.echo(
                click.style("[OK]", fg="green")
                + f" Results dir: {ROOT_DIRECTORY_RESULTS}"
            )
            click.echo(
                click.style("[OK]", fg="green") + f" LPM data: {DIRECTORY_LPM_DATA}"
            )
            click.echo(
                click.style("[OK]", fg="green")
                + f" Tracer data: {DIRECTORY_TRACER_DATA}"
            )
        else:
            click.echo(click.style("[OK]", fg="green") + " Data directories configured")
        checks_passed += 1
    except Exception as e:
        click.echo(click.style("[FAIL]", fg="red") + f" Path config: {e}")
        checks_failed += 1

    # Summary
    click.echo()
    click.echo("=" * 40)
    total = checks_passed + checks_failed
    if checks_failed == 0:
        click.echo(
            click.style(f"All {total} checks passed.", fg="green", bold=True)
            + " PyAge is ready!"
        )
        sys.exit(0)
    else:
        click.echo(
            click.style(f"{checks_failed}/{total} checks failed.", fg="red", bold=True)
        )
        sys.exit(1)
