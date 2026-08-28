# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Typed public entry points for reusable high-level PyAges workflows."""

from __future__ import annotations

from pathlib import Path


def run_single_date(
    params_path: str | Path,
    force_inline: bool = False,
) -> Path:
    """Run the single-date workflow without importing it at package import time."""
    from pyages.workflows.single_date import run_single_date as implementation

    return implementation(params_path, force_inline=force_inline)


def run_temporal(params_path: str | Path) -> Path:
    """Run the temporal workflow without importing it at package import time."""
    from pyages.workflows.temporal import run_temporal as implementation

    return implementation(params_path)


__all__ = ["run_single_date", "run_temporal"]
