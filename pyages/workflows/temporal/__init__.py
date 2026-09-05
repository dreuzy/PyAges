# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes the public temporal workflow function from its runner.
# The function accepts a YAML configuration path, calibrates the requested time
# cases and models, and returns the published result or sole-case directory.

"""Public entry point for temporal calibration."""

from pyages.workflows.temporal.runner import run_temporal

__all__ = ["run_temporal"]
