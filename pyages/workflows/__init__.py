# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Reusable high-level PyAges workflows with lazy imports."""


def run_single_date(*args, **kwargs):
    """Run the single-date workflow without importing it at package import time."""
    from pyages.workflows.single_date import run_single_date as implementation

    return implementation(*args, **kwargs)


def run_temporal(*args, **kwargs):
    """Run the temporal workflow without importing it at package import time."""
    from pyages.workflows.temporal import run_temporal as implementation

    return implementation(*args, **kwargs)


__all__ = ["run_single_date", "run_temporal"]
