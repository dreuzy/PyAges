"""
PyAge run command - Execute simulations from YAML config.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import click
import yaml
from pydantic import ValidationError

from pyage.config.loading import load_yaml_mapping
from pyage.config.models import CliRunParams


@click.command()
@click.argument("config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--transient",
    is_flag=True,
    help="Run the canonical multi-date temporal workflow.",
)
@click.option(
    "--inline",
    is_flag=True,
    help="Force inline matplotlib backend (useful in notebooks/IDEs).",
)
@click.option(
    "--lpm",
    default=None,
    help="Override LPM model name (single-date) or list (transient).",
)
@click.option(
    "--mh-nsteps",
    type=int,
    default=None,
    help="Override Metropolis-Hastings iteration count.",
)
@click.option(
    "--data-name",
    default=None,
    help="Override dataset filename (single-date only).",
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Override dataset directory (single-date only).",
)
@click.option(
    "--data-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Override dataset path (transient only).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
def run(
    config: Path,
    transient: bool,
    inline: bool,
    lpm: str | None,
    mh_nsteps: int | None,
    data_name: str | None,
    data_dir: Path | None,
    data_file: Path | None,
    verbose: bool,
):
    """Run PyAge simulation from a YAML configuration file.

    CONFIG is the path to the YAML parameters file.

    \b
    Examples:
        pyage run examples/natural/ploemeur/exemple_ploemeur.yaml
        pyage run --transient examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
    """
    # Ensure config path is absolute
    config = config.resolve()
    try:
        params = CliRunParams.model_validate(
            {
                "config": config,
                "transient": transient,
                "inline": inline,
                "lpm": lpm,
                "mh_nsteps": mh_nsteps,
                "data_name": data_name,
                "data_dir": data_dir,
                "data_file": data_file,
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
    lpm = params.lpm
    mh_nsteps = params.mh_nsteps
    data_name = params.data_name
    data_dir = params.data_dir
    data_file = params.data_file

    if verbose:
        click.echo(f"Configuration file: {config}")
        click.echo(f"Mode: {'transient' if transient else 'single-date'}")

    original_config = config
    config = _apply_overrides(
        config=config,
        transient=transient,
        lpm=lpm,
        mh_nsteps=mh_nsteps,
        data_name=data_name,
        data_dir=data_dir,
        data_file=data_file,
        verbose=verbose,
    )

    try:
        if transient:
            _run_transient(config, verbose)
        else:
            _run_single_date(config, inline, verbose)
    finally:
        if config != original_config:
            config.unlink(missing_ok=True)


def _load_yaml(path: Path) -> dict:
    return load_yaml_mapping(path)


def _apply_overrides(
    config: Path,
    transient: bool,
    lpm: str | None,
    mh_nsteps: int | None,
    data_name: str | None,
    data_dir: Path | None,
    data_file: Path | None,
    verbose: bool,
) -> Path:
    if not any([lpm, mh_nsteps, data_name, data_dir, data_file]):
        return config

    data = _load_yaml(config)

    if transient:
        if data_name or data_dir:
            click.echo(
                click.style(
                    "Ignoring --data-name/--data-dir (single-date only) in transient mode.",
                    fg="yellow",
                )
            )
        if data_file:
            data.setdefault("dataset", {})["file"] = str(data_file)
        if lpm:
            data.setdefault("lpm_models", {})["list"] = [lpm]
        if mh_nsteps is not None:
            data.setdefault("calibration", {})["mh_nsteps"] = int(mh_nsteps)
    else:
        if data_file:
            click.echo(
                click.style(
                    "Ignoring --data-file (transient only) in single-date mode.",
                    fg="yellow",
                )
            )
        if data_name:
            data.setdefault("dataset", {})["name"] = data_name
        if data_dir:
            data.setdefault("dataset", {})["data_dir"] = str(data_dir)
        if lpm:
            data.setdefault("lpm", {})["model_name"] = lpm
        if mh_nsteps is not None:
            data.setdefault("calibration_metropolis_hastings", {})["nstep"] = int(
                mh_nsteps
            )

    # Keep the temporary file beside the source configuration so all relative
    # data paths retain the same resolution root after applying overrides.
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=config.parent,
        prefix=f".{config.stem}-",
        suffix=".yaml",
    ) as tmp:
        tmp_path = Path(tmp.name)
    tmp_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    if verbose:
        click.echo(f"Using overridden config: {tmp_path}")

    return tmp_path


def _run_single_date(config: Path, inline: bool, verbose: bool):
    """Run the canonical single-date workflow."""
    try:
        from pyage.workflows.single_date import run_single_date

        click.echo("Running single-date workflow...")
        click.echo(f"Config: {config}")
        run_single_date(str(config), force_inline=inline)

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
    """Run the canonical transient (multi-date) workflow."""
    try:
        from pyage.workflows.temporal import run_temporal

        click.echo("Running transient (multi-date) workflow...")
        click.echo(f"Config: {config}")
        run_temporal(config)

    except ImportError as e:
        click.echo(click.style(f"Import error: {e}", fg="red"))
        click.echo("Make sure you have installed pyage: pip install -e .")
        sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"Error running transient workflow: {e}", fg="red"))
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)
