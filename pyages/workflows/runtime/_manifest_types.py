# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the immutable records exchanged by manifest operations.

"""Represent active runs, persisted journal state, and staging diagnostics.

``ResultRun`` is an opaque capability returned when staging begins and later
required for terminal-manifest writing and publication. ``RunState`` represents
the validated journal stored on disk, including the original public-tree token.
``StagedRunInspection`` carries a read-only diagnosis for operator tooling.

Separating these records from filesystem operations makes their invariants
explicit and prevents ordinary callers from constructing a publishable run
handle directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True, init=False)
class ResultRun:
    """Opaque handle for an isolated staged result run.

    Callers may use its identity and resolved directories, but must obtain it
    from ``begin_staged_result_run`` and pass the unchanged handle to
    ``promote_result_run`` after writing the terminal manifest.
    """

    run_id: str
    started_at_utc: str
    result_directory: Path
    working_directory: Path
    _expected_publication_token: str = field(repr=False)

    def __init__(self) -> None:
        """Reject direct construction; use ``begin_staged_result_run``."""
        raise TypeError("ResultRun handles are created by begin_staged_result_run().")


@dataclass(frozen=True)
class StagedRunInspection:
    """Read-only diagnosis of one managed staging-directory candidate.

    Explicit status strings distinguish missing evidence from evidence that
    was checked and found inconsistent. ``promotable_now`` is a point-in-time
    diagnosis; promotion repeats every safety check under the hierarchy lock.
    """

    stage_directory: Path
    journal_status: Literal["valid", "missing", "invalid"]
    run_id: str | None
    started_at_utc: str | None
    result_directory: Path | None
    manifest_status: Literal["not_checked", "absent", "unsealed", "sealed", "invalid"]
    artifacts_status: Literal["not_checked", "match", "mismatch"]
    publication_status: Literal["not_checked", "current", "changed"]
    promotable_now: bool
    issues: tuple[str, ...]


@dataclass(frozen=True)
class RunState:
    """Validated private journal state for a result run.

    ``implicit`` represents a direct manifest write without a journal.
    ``staged`` binds an isolated working tree to its public destination and
    compare-and-swap token.
    """

    run_id: str
    started_at_utc: str
    mode: Literal["implicit", "staged"]
    result_directory: Path
    expected_publication_token: str | None
    terminal_manifest_sha256: str | None
    managed: bool


def new_result_run(
    *,
    run_id: str,
    started_at_utc: str,
    result_directory: Path,
    working_directory: Path,
    expected_publication_token: str,
) -> ResultRun:
    """Construct the opaque staged-run handle for the runtime façade."""
    run = object.__new__(ResultRun)
    object.__setattr__(run, "run_id", run_id)
    object.__setattr__(run, "started_at_utc", started_at_utc)
    object.__setattr__(run, "result_directory", result_directory)
    object.__setattr__(run, "working_directory", working_directory)
    object.__setattr__(
        run,
        "_expected_publication_token",
        expected_publication_token,
    )
    return run
