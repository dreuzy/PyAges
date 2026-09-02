# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the two failure categories used while constructing tracers.

"""Distinguish invalid tracer definitions from unavailable or unusable data.

``TracerConfigError`` reports a definition that was read successfully but asks
for an unsupported tracer type, option, unit, or decay configuration.
``TracerDataError`` reports failures to find or parse configuration and
chronicle files, as well as non-numeric, non-finite, or otherwise unusable
recharge histories.

Keeping these categories separate lets callers explain whether the user should
correct the YAML definition or inspect the underlying files and measurements.
"""


class TracerConfigError(Exception):
    """A readable tracer definition contains an invalid or unsupported choice."""


class TracerDataError(Exception):
    """Tracer configuration or chronicle data is unavailable or unusable."""
