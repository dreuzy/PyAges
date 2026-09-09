# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the public import surface for lumped-parameter models (LPMs).
# Callers can build a configured or random water-age model by its short name and
# store calibration rows without importing the internal registry or core classes.

"""Lumped-parameter models, construction, and calibrated sample tables."""

from pyages.lpm.factory import build_lpm, build_random_lpm, list_available_lpms
from pyages.lpm.samples import LpmSampleTable

__all__ = [
    "LpmSampleTable",
    "build_lpm",
    "build_random_lpm",
    "list_available_lpms",
]
