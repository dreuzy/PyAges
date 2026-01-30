"""
PyAge new commands - Generate templates for new LPMs and tracers.
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
    type=click.Choice(["scipy", "scipy_safe", "root"]),
    default="scipy",
    help="Base class to extend (default: scipy).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory (default: pyage/lpm/models/).",
)
def new_lpm(name: str, base: str, output: str):
    """Generate a template for a new LPM model.

    NAME is the identifier for the new model (e.g., 'weibull', 'lognormal').

    \b
    Creates:
      - pyage/lpm/models/LPM_<name>.py
      - data_core/data_lpm/<name>/params.yaml

    \b
    Examples:
        pyage new lpm weibull
        pyage new lpm lognormal --base scipy_safe
        pyage new lpm custom --base root
    """
    from pyage.cli.templates.lpm_template import generate_lpm_template

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
    help="Output directory (default: data_core/data_tracer/).",
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
        pyage new tracer he4
        pyage new tracer ar39 --with-decay
        pyage new tracer custom --no-chronicle
    """
    from pyage.cli.templates.tracer_template import generate_tracer_template

    generate_tracer_template(name, output, not no_chronicle, with_decay)
