"""
PyAge CLI - Main entry point.

Usage:
    pyage --help
    pyage run config.yaml
    pyage list lpms
    pyage list tracers
    pyage new lpm my_model
    pyage new tracer my_tracer
    pyage check
"""

import click

from pyage.cli.commands.check import check
from pyage.cli.commands.list_cmd import list_group
from pyage.cli.commands.new import new_group
from pyage.cli.commands.run import run


@click.group()
@click.version_option(version="0.1.0", prog_name="pyage")
def cli():
    """PyAge - Groundwater Age Dating Toolkit.

    A Python package for groundwater age dating using lumped parameter models
    and environmental tracers.

    \b
    Quick start:
        pyage check                    # Verify installation
        pyage list lpms                # See available models
        pyage list tracers             # See available tracers
        pyage run config.yaml          # Run a simulation
    """
    pass


# Register commands
cli.add_command(run)
cli.add_command(list_group)
cli.add_command(new_group)
cli.add_command(check)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
