# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Canonical contributor-facing execution services for workflows.

Only the staged-run and manifest lifecycle is re-exported here. Algorithm and
plotting helpers remain in their dedicated submodules so this facade does not
turn runtime implementation details into compatibility promises.
"""

from pyages.workflows.runtime.manifest import (
    ResultRun,
    begin_staged_result_run,
    promote_result_run,
    write_failure_manifest,
    write_result_manifest,
)

__all__ = [
    "ResultRun",
    "begin_staged_result_run",
    "promote_result_run",
    "write_failure_manifest",
    "write_result_manifest",
]
