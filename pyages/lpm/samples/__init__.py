# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file exposes the public container for LPM calibration samples.
# The table keeps tested parameters beside fit scores and predicted tracer
# concentrations, then provides best-model and population-level summaries.

"""LPM sample-table storage and analysis."""

from pyages.lpm.samples.table import LpmSampleTable

__all__ = ["LpmSampleTable"]
