# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes the public single-date workflow function from its runner.
# The function accepts a YAML configuration path, performs the full calibration
# pipeline, and returns the directory in which the result was published.

"""Public entry point for single-date calibration."""

from pyages.workflows.single_date.runner import run_single_date

__all__ = ["run_single_date"]
