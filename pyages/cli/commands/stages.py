# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Inspect and explicitly quarantine interrupted workflow staging trees."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from pyages.workflows.runtime.manifest import (
    StagedRunInspection,
    inventory_staged_result_runs,
    quarantine_staged_result_run,
)


def _inspection_payload(inspection: StagedRunInspection) -> dict[str, Any]:
    """Convert an inspection to a stable JSON-compatible CLI payload."""
    return {
        "stage_directory": str(inspection.stage_directory),
        "journal_status": inspection.journal_status,
        "run_id": inspection.run_id,
        "started_at_utc": inspection.started_at_utc,
        "result_directory": (
            str(inspection.result_directory)
            if inspection.result_directory is not None
            else None
        ),
        "manifest_status": inspection.manifest_status,
        "artifacts_status": inspection.artifacts_status,
        "publication_status": inspection.publication_status,
        "promotable_now": inspection.promotable_now,
        "issues": list(inspection.issues),
    }


def _echo_inspection(inspection: StagedRunInspection) -> None:
    """Print one concise operator-readable diagnosis."""
    click.echo(str(inspection.stage_directory))
    click.echo(f"  run_id: {inspection.run_id or '-'}")
    click.echo(f"  started_at_utc: {inspection.started_at_utc or '-'}")
    click.echo(f"  result_directory: {inspection.result_directory or '-'}")
    click.echo(f"  journal: {inspection.journal_status}")
    click.echo(f"  manifest: {inspection.manifest_status}")
    click.echo(f"  artifacts: {inspection.artifacts_status}")
    click.echo(f"  publication: {inspection.publication_status}")
    click.echo(f"  promotable_now: {'yes' if inspection.promotable_now else 'no'}")
    for issue in inspection.issues:
        click.echo(f"  issue: {issue}")


@click.group(name="stages")
def stages_group() -> None:
    """Inspect or quarantine workflow staging directories."""


@stages_group.command(name="inspect")
@click.argument(
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Emit a machine-readable JSON array.",
)
def inspect_stages(root: Path, json_output: bool) -> None:
    """Recursively inspect staging candidates below ROOT without writing."""
    try:
        inspections = inventory_staged_result_runs(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    if json_output:
        click.echo(
            json.dumps(
                [_inspection_payload(item) for item in inspections],
                indent=2,
                sort_keys=True,
            )
        )
        return
    if not inspections:
        click.echo("No managed staging candidates found.")
        return
    for index, inspection in enumerate(inspections):
        if index:
            click.echo()
        _echo_inspection(inspection)


@stages_group.command(name="quarantine")
@click.argument(
    "stage_directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--run-id",
    required=True,
    help="Complete run UUID printed by the inspect command.",
)
@click.confirmation_option(
    prompt="Stop the owning workflow and quarantine this complete staging tree?"
)
def quarantine_stage(stage_directory: Path, run_id: str) -> None:
    """Atomically quarantine STAGE_DIRECTORY after explicit confirmation."""
    try:
        quarantine = quarantine_staged_result_run(
            stage_directory,
            run_id=run_id,
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Quarantined staging tree: {quarantine}")


__all__ = ["stages_group"]
