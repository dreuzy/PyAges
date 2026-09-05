# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file implements the command that launches a configured PyAges workflow.

"""Execute the workflow declared by a ``pyages run`` configuration.

The command reads the supplied YAML file once, detects its workflow, validates
command-line overrides, and applies those overrides to a temporary configuration
so the user's original file is never rewritten.

Configuration and validation errors are formatted for command-line users before
scientific execution begins. On completion, the workflow's terminal status is
translated into a stable process exit code for shells and automation scripts.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Literal

import click
import yaml
from pydantic import ValidationError

from pyages.config.loading import load_yaml_mapping
from pyages.config.models import CliRunParams

WorkflowKind = Literal["single_date", "temporal"]


@click.command()
@click.argument("config", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--inline",
    is_flag=True,
    help="Force inline matplotlib backend (useful in notebooks/IDEs).",
)
@click.option(
    "--lpm",
    default=None,
    help="Override LPM model name (single-date) or list (temporal).",
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
    help="Override dataset path (temporal only).",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
def run(
    config: Path,
    inline: bool,
    lpm: str | None,
    mh_nsteps: int | None,
    data_name: str | None,
    data_dir: Path | None,
    data_file: Path | None,
    verbose: bool,
):
    """Run PyAges simulation from a YAML configuration file.

    CONFIG is the path to the YAML parameters file.

    \b
    Examples:
        pyages run examples/natural/ploemeur/exemple_ploemeur.yaml
        pyages run examples/natural/ploemeur_temporal/ploemeur_temporal.yaml
    """
    # Ensure config path is absolute
    config = config.resolve()
    try:
        params = CliRunParams.model_validate(
            {
                "config": config,
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
    inline = params.inline
    verbose = params.verbose
    lpm = params.lpm
    mh_nsteps = params.mh_nsteps
    data_name = params.data_name
    data_dir = params.data_dir
    data_file = params.data_file

    data = load_yaml_mapping(config)
    workflow = _detect_workflow(data)

    if verbose:
        click.echo(f"Configuration file: {config}")
        click.echo(f"Workflow: {workflow}")

    changed = _apply_overrides(
        data=data,
        workflow=workflow,
        lpm=lpm,
        mh_nsteps=mh_nsteps,
        data_name=data_name,
        data_dir=data_dir,
        data_file=data_file,
    )
    original_config = config
    if changed:
        config = _write_temporary_config(config, data)
        if verbose:
            click.echo(f"Using overridden config: {config}")

    try:
        _run_workflow(workflow, config, inline=inline, verbose=verbose)
    finally:
        if config != original_config:
            config.unlink(missing_ok=True)


def _detect_workflow(data: dict) -> WorkflowKind:
    """Return the workflow explicitly declared by the YAML mapping."""
    workflow = data.get("workflow")
    declared = workflow.get("kind") if isinstance(workflow, dict) else None
    if declared not in {"single_date", "temporal"}:
        raise click.ClickException(
            "workflow.kind is required and must be 'single_date' or 'temporal'"
        )
    return declared


def _apply_overrides(
    data: dict,
    workflow: WorkflowKind,
    lpm: str | None,
    mh_nsteps: int | None,
    data_name: str | None,
    data_dir: Path | None,
    data_file: Path | None,
) -> bool:
    """Apply command-line overrides and report whether the mapping changed."""
    if not any([lpm, mh_nsteps, data_name, data_dir, data_file]):
        return False

    if workflow == "temporal":
        _apply_temporal_overrides(data, lpm, mh_nsteps, data_file)
        if data_name or data_dir:
            _warn("Ignoring --data-name/--data-dir (single-date only).")
    else:
        _apply_single_date_overrides(data, lpm, mh_nsteps, data_name, data_dir)
        if data_file:
            _warn("Ignoring --data-file (temporal only).")
    return True


def _apply_temporal_overrides(
    data: dict, lpm: str | None, mh_nsteps: int | None, data_file: Path | None
) -> None:
    if data_file:
        data.setdefault("dataset", {})["file"] = str(data_file)
    if lpm:
        data.setdefault("lpm_models", {})["list"] = [lpm]
    if mh_nsteps is not None:
        data.setdefault("calibration", {})["mh_nsteps"] = int(mh_nsteps)


def _apply_single_date_overrides(
    data: dict,
    lpm: str | None,
    mh_nsteps: int | None,
    data_name: str | None,
    data_dir: Path | None,
) -> None:
    if data_name:
        data.setdefault("dataset", {})["name"] = data_name
    if data_dir:
        data.setdefault("dataset", {})["data_dir"] = str(data_dir)
    if lpm:
        data.setdefault("lpm", {})["model_name"] = lpm
    if mh_nsteps is not None:
        data.setdefault("calibration_metropolis_hastings", {})["nstep"] = int(mh_nsteps)


def _warn(message: str) -> None:
    click.echo(click.style(message, fg="yellow"))


def _write_temporary_config(config: Path, data: dict) -> Path:
    """Write overrides beside their source so relative paths remain stable."""
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=config.parent,
        prefix=f".{config.stem}-",
        suffix=".yaml",
    ) as tmp:
        tmp_path = Path(tmp.name)
    tmp_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return tmp_path


def _run_workflow(
    workflow: WorkflowKind, config: Path, *, inline: bool, verbose: bool
) -> None:
    """Run one validated workflow with shared reporting and error handling."""
    try:
        label = "single-date" if workflow == "single_date" else "temporal"
        click.echo(f"Running {label} workflow...")
        click.echo(f"Config: {config}")
        if workflow == "single_date":
            from pyages.workflows.single_date import run_single_date

            output_directory = run_single_date(str(config), force_inline=inline)
        else:
            from pyages.workflows.temporal import run_temporal

            output_directory = run_temporal(config)
        click.echo(f"Results written to: {output_directory}")
    except ImportError as e:
        click.echo(click.style(f"Import error: {e}", fg="red"))
        click.echo("Make sure you have installed pyages: pip install -e .")
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error running {workflow} workflow: {e}", fg="red"))
        if verbose:
            import traceback

            traceback.print_exc()
        else:
            _echo_exception_notes(e)
        sys.exit(1)


def _echo_exception_notes(error: BaseException) -> None:
    """Print distinct exception notes hidden by ``str(error)``."""
    seen: set[str] = set()
    for note in getattr(error, "__notes__", ()):
        text = str(note)
        if text and text not in seen:
            click.echo(click.style(f"  {text}", fg="red"))
            seen.add(text)
