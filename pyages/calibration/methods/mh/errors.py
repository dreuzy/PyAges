# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# Purpose: Define failures raised when MH diagnostics block qualified output.

"""Exceptions raised by multi-chain Metropolis--Hastings workflows."""

from __future__ import annotations


class MHConvergenceError(RuntimeError):
    """Raised when qualified posterior output is requested before convergence."""


class MHDiagnosticsUnavailableError(RuntimeError):
    """Raised when valid draws cannot yield numerical convergence diagnostics."""


__all__ = ["MHConvergenceError", "MHDiagnosticsUnavailableError"]
