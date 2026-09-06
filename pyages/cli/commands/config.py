# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file provides explicit, non-destructive configuration maintenance commands.

"""Inspect and migrate versioned PyAges workflow configurations."""

from __future__ import annotations

from pathlib import Path

import click
import yaml
from pydantic import ValidationError

from pyages.config.loading import load_yaml_mapping
from pyages.config.migration import (
    configuration_base_directory,
    configuration_workflow_kind,
    migrate_configuration_payload,
    normalize_configuration_payload,
)
from pyages.config.models import LauncherConfig, TemporalParams


@click.group(name="config")
def config_group() -> None:
    """Validate and migrate workflow configuration files."""


@config_group.command(name="migrate")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("destination", type=click.Path(dir_okay=False, path_type=Path))
def migrate_config(source: Path, destination: Path) -> None:
    """Copy legacy SOURCE to schema-2 DESTINATION without changing SOURCE.

    SOURCE and DESTINATION must share a directory so relative scientific input
    paths retain exactly the same meaning. YAML comments cannot be retained by
    the semantic migration and should be reviewed in the generated file.
    """
    source = source.resolve()
    destination = destination.resolve()
    if destination == source:
        raise click.ClickException("Destination must differ from the source file.")
    if destination.parent != source.parent:
        raise click.ClickException(
            "Destination must be beside the source so relative paths keep "
            "their meaning."
        )
    if destination.exists():
        raise click.ClickException(f"Destination already exists: {destination}")

    try:
        canonical = migrate_configuration_payload(load_yaml_mapping(source))
        kind = configuration_workflow_kind(canonical)
        runtime = normalize_configuration_payload(canonical, expected_kind=kind)
        if kind == "single_date":
            LauncherConfig.model_validate(
                runtime,
                context={"root_dir": configuration_base_directory(source, canonical)},
            )
        else:
            TemporalParams.model_validate(runtime)
    except (TypeError, ValueError, ValidationError) as exc:
        raise click.ClickException(f"Cannot migrate configuration: {exc}") from exc

    destination.write_text(
        yaml.safe_dump(canonical, sort_keys=False),
        encoding="utf-8",
    )
    click.echo(f"Created schema-2 configuration: {destination}")
    click.echo(f"Source left unchanged: {source}")
    click.echo("Review the generated file because YAML comments are not preserved.")


__all__ = ["config_group", "migrate_config"]
