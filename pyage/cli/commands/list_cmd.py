"""
PyAge list commands - List available LPMs and tracers.
"""

import sys
from pathlib import Path

import click


def _setup_import_paths():
    """Setup sys.path for imports to work correctly."""
    cli_dir = Path(__file__).resolve().parent
    pyage_dir = cli_dir.parent.parent
    repo_root = pyage_dir.parent

    paths_to_add = [str(repo_root), str(pyage_dir)]
    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)


@click.group(name="list")
def list_group():
    """List available models and tracers."""
    pass


@list_group.command(name="lpms")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_lpms(verbose: bool):
    """List all available LPM (Lumped Parameter Model) types.

    \b
    Example:
        pyage list lpms
        pyage list lpms --verbose
    """
    _setup_import_paths()
    from LPM.core.registry import get_lpm_class
    from LPM.lpm_build import list_available_lpms

    lpms = list_available_lpms()
    click.echo(f"Available LPM models ({len(lpms)}):")
    click.echo()

    for name in lpms:
        if verbose:
            try:
                cls = get_lpm_class(name)
                doc = cls.__doc__ or "No description"
                first_line = doc.strip().split("\n")[0]
                click.echo(f"  {name:24s} {first_line}")
            except Exception:
                click.echo(f"  {name}")
        else:
            click.echo(f"  - {name}")


@list_group.command(name="tracers")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_tracers(verbose: bool):
    """List all available tracers in the data directory.

    \b
    Example:
        pyage list tracers
        pyage list tracers --verbose
    """
    _setup_import_paths()
    from tracer.tracer_root import Tracer, find_tracer_dir

    tracer_dir = find_tracer_dir()
    tracer_names = sorted(
        [
            d.name
            for d in tracer_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
    )

    click.echo(f"Available tracers ({len(tracer_names)}):")
    if verbose:
        click.echo(f"Location: {tracer_dir}")
    click.echo()

    for name in tracer_names:
        if verbose:
            try:
                tracer = Tracer(tracer_dir, name=name)
                click.echo(
                    f"  {name:12s} unit: {tracer.unit:6s}  "
                    f"range: {tracer.datemin:.0f}-{tracer.datemax:.0f}"
                )
            except Exception as e:
                click.echo(f"  {name:12s} (error: {e})")
        else:
            click.echo(f"  - {name}")
