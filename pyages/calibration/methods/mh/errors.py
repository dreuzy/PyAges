# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Exceptions raised by multi-chain Metropolis--Hastings workflows."""

from __future__ import annotations


class MHConvergenceError(RuntimeError):
    """Raised when qualified posterior output is requested before convergence."""


class MHDiagnosticsUnavailableError(RuntimeError):
    """Raised when valid draws cannot yield numerical convergence diagnostics."""


__all__ = ["MHConvergenceError", "MHDiagnosticsUnavailableError"]
