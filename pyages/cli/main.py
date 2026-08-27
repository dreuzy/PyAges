# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""
PyAges CLI - Main entry point.

Usage:
    pyages --help
    pyages run config.yaml
    pyages list lpms
    pyages list tracers
    pyages new lpm my_model
    pyages new tracer my_tracer
    pyages check
"""

import click

from pyages import __version__
from pyages.cli.commands.check import check
from pyages.cli.commands.list_cmd import list_group
from pyages.cli.commands.new import new_group
from pyages.cli.commands.run import run


@click.group()
@click.version_option(version=__version__, prog_name="pyages")
def cli():
    """PyAges - Groundwater Age Dating Toolkit.

    A Python package for groundwater age dating using lumped parameter models
    and environmental tracers.

    \b
    Quick start:
        pyages check                    # Verify installation
        pyages list lpms                # See available models
        pyages list tracers             # See available tracers
        pyages run config.yaml          # Run a simulation
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
