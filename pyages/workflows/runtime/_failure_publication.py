# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file preserves terminal scientific failures through the staged-run API.

"""Publish convergence-failure evidence consistently across workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pyages.workflows.runtime.manifest import (
    ResultRun,
    promote_result_run,
    write_failure_manifest,
)


def preserve_failure_result(
    run: ResultRun,
    *,
    workflow: str,
    config_path: str | Path,
    error: BaseException,
    input_paths: Iterable[str | Path] = (),
    details: Mapping[str, Any] | None = None,
) -> Path | None:
    """Seal and publish rejected-run evidence, recording any publication error."""
    try:
        write_failure_manifest(
            run.working_directory,
            workflow=workflow,
            config_path=config_path,
            input_paths=input_paths,
            details=details,
            error=error,
            run_id=run.run_id,
        )
        failure_directory = promote_result_run(run)
        error.add_note(f"Preserved result evidence: {failure_directory}")
        return failure_directory
    except Exception as manifest_error:
        error.add_note(f"Could not write failure manifest: {manifest_error}")
        return None


__all__ = ["preserve_failure_result"]
