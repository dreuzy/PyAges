# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Public entry point for single-date calibration."""

from pyages.workflows.single_date.runner import run_single_date

__all__ = ["run_single_date"]
