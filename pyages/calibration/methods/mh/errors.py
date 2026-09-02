# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file names the diagnostic failures reported by multi-chain MH runs.

"""Define the errors used when an MH ensemble cannot produce qualified output.

One error means that calculated diagnostics did not meet the configured
thresholds. The other means that the diagnostics could not be calculated from
the available draws.
"""

from __future__ import annotations


class MHConvergenceError(RuntimeError):
    """The chains failed a diagnostic threshold required for posterior output."""


class MHDiagnosticsUnavailableError(RuntimeError):
    """The retained draws could not produce finite convergence diagnostics."""


__all__ = ["MHConvergenceError", "MHDiagnosticsUnavailableError"]
