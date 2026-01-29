"""
PyAge run command - Execute simulations from YAML config.
"""

from pathlib import Path
import sys

import click
from pydantic import ValidationError

from pyage.config.models import CliRunParams


@click.command()
@click.argument("config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--transient",
    is_flag=True,
    help="Run in transient (multi-date) mode using launcher_temporal.",
)
@click.option(
    "--inline",
    is_flag=True,
    help="Force inline matplotlib backend (useful in notebooks/IDEs).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
def run(config: Path, transient: bool, inline: bool, verbose: bool):
    """Run PyAge simulation from a YAML configuration file.

    CONFIG is the path to the YAML parameters file.

    \b
    Examples:
        pyage run examples/ploemeur/exemple_ploemeur.yaml
        pyage run --transient examples/ploemeur_temporal/ploemeur_temporal.yaml
    """
    # Ensure config path is absolute
    config = config.resolve()
    try:
        params = CliRunParams.model_validate(
            {
                "config": config,
                "transient": transient,
                "inline": inline,
                "verbose": verbose,
            }
        )
    except ValidationError as exc:
        click.echo(click.style(f"Invalid CLI arguments:\n{exc}", fg="red"))
        sys.exit(1)

    config = params.config
    transient = params.transient
    inline = params.inline
    verbose = params.verbose

    if verbose:
        click.echo(f"Configuration file: {config}")
        click.echo(f"Mode: {'transient' if transient else 'single-date'}")

    if transient:
        _run_transient(config, verbose)
    else:
        _run_single_date(config, inline, verbose)


def _run_single_date(config: Path, inline: bool, verbose: bool):
    """Run single-date workflow via launcher.py."""
    try:
        # Import the launcher module
        from scripts.launcher import run_workflow

        click.echo(f"Running single-date workflow...")
        click.echo(f"Config: {config}")
        run_workflow(str(config), force_inline=inline)

    except ImportError as e:
        click.echo(click.style(f"Import error: {e}", fg="red"))
        click.echo("Make sure you have installed pyage: pip install -e .")
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error running workflow: {e}", fg="red"))
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _run_transient(config: Path, verbose: bool):
    """Run transient (multi-date) workflow via launcher_temporal.py."""
    try:
        # Import the temporal launcher
        from scripts.launcher_temporal import run_temporal_workflow

        click.echo(f"Running transient (multi-date) workflow...")
        click.echo(f"Config: {config}")
        run_temporal_workflow(str(config))

    except ImportError as e:
        # Fallback: try to import and call the main function directly
        click.echo(click.style(f"Import error: {e}", fg="yellow"))
        click.echo("Attempting alternative import...")

        try:
            import scripts.launcher_temporal as lt
            # Check if there's a main-like function we can call
            if hasattr(lt, "main"):
                lt.main(str(config))
            else:
                click.echo(click.style(
                    "Could not find entry point in launcher_temporal.py",
                    fg="red"
                ))
                sys.exit(1)
        except Exception as e2:
            click.echo(click.style(f"Error: {e2}", fg="red"))
            if verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"Error running transient workflow: {e}", fg="red"))
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
