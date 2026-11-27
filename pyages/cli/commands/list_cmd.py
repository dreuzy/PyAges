# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file implements commands that list the scientific resources PyAges can load.

"""Display valid LPM and tracer identifiers through the ``pyages list`` command.

Model names are read from the live LPM registry rather than a duplicated static
list. Tracer names are discovered from the installed data resources and pass
through their normal validation boundary.

The output therefore reflects the capabilities of the current installation and
can be copied directly into workflow configuration files.
"""

import click


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
        pyages list lpms
        pyages list lpms --verbose
    """
    from pyages.lpm.core.registry import get_lpm_class
    from pyages.lpm.factory import list_available_lpms

    lpms = list_available_lpms()
    click.echo(f"Available LPM models ({len(lpms)}):")
    click.echo()

    for name in lpms:
        if verbose:
            cls = get_lpm_class(name)
            doc = cls.__doc__ or "No description"
            first_line = doc.strip().split("\n")[0]
            click.echo(f"  {name:24s} {first_line}")
        else:
            click.echo(f"  - {name}")


@list_group.command(name="tracers")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_tracers(verbose: bool):
    """List all available tracers in the data directory.

    \b
    Example:
        pyages list tracers
        pyages list tracers --verbose
    """
    from pyages.config.paths import DIRECTORY_TRACER_DATA
    from pyages.tracer.tracer_root import Tracer

    tracer_dir = DIRECTORY_TRACER_DATA
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
            tracer = Tracer(tracer_dir, name=name)
            click.echo(
                f"  {name:12s} unit: {tracer.unit:6s}  "
                f"range: {tracer.datemin:.0f}-{tracer.datemax:.0f}"
            )
        else:
            click.echo(f"  - {name}")
