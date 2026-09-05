# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file implements commands that scaffold a new LPM or tracer definition.

"""Generate editable extension templates through the ``pyages new`` command.

The LPM subcommand creates a Python model skeleton together with its parameter
YAML, while the tracer subcommand creates metadata and recharge-history examples.
Content generation is delegated to the template modules so command behavior and
generated documentation remain separate.

Existing targets are protected by the command's explicit replacement rules,
preventing ordinary scaffolding from silently overwriting contributor work.
"""

import click


@click.group(name="new")
def new_group():
    """Generate templates for new models and tracers."""
    pass


@new_group.command(name="lpm")
@click.argument("name")
@click.option(
    "--base",
    type=click.Choice(["scipy", "root"]),
    default="scipy",
    help="Base class to extend (default: scipy).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help=(
        "Model-module output directory; params remain under "
        "./data_core/data_lpm/ (default: ./pyages/lpm/models/)."
    ),
)
def new_lpm(name: str, base: str, output: str):
    """Generate a template for a new LPM model.

    NAME is the identifier for the new model (e.g., 'weibull', 'lognormal').

    Run this source-development command from an editable checkout. A custom
    output directory must be integrated into pyages.lpm.models for discovery.

    \b
    Creates:
      - pyages/lpm/models/<name>.py
      - data_core/data_lpm/<name>/params.yaml

    \b
    Examples:
        pyages new lpm weibull
        pyages new lpm lognormal --base scipy
        pyages new lpm custom --base root
    """
    from pyages.cli.templates.lpm_template import generate_lpm_template

    generate_lpm_template(name, output, base)


@new_group.command(name="tracer")
@click.argument("name")
@click.option(
    "--with-decay",
    is_flag=True,
    help="Include radioactive decay configuration.",
)
@click.option(
    "--no-chronicle",
    is_flag=True,
    help="Skip recharge chronicle template (use constant concentration).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help=(
        "Tracer root directory; configure tracers.data_directory when custom "
        "(default: ./data_core/data_tracer/)."
    ),
)
def new_tracer(name: str, with_decay: bool, no_chronicle: bool, output: str):
    """Generate a template for a new tracer.

    NAME is the identifier for the new tracer (e.g., 'he4', 'ar39').

    \b
    Creates:
      - data_core/data_tracer/<name>/<name>.yaml
      - data_core/data_tracer/<name>/recharge.csv (unless --no-chronicle)

    \b
    Examples:
        pyages new tracer he4
        pyages new tracer ar39 --with-decay
        pyages new tracer custom --no-chronicle
    """
    from pyages.cli.templates.tracer_template import generate_tracer_template

    generate_tracer_template(name, output, not no_chronicle, with_decay)
