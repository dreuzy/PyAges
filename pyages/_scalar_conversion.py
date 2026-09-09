# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file centralizes explicit conversion of values known to be scalar.

"""Convert values whose third-party type hints retain non-scalar alternatives."""

from __future__ import annotations

from typing import SupportsFloat, SupportsIndex, SupportsInt, cast


def scalar_float(value: object) -> float:
    """Return a value that the caller has established is a numeric scalar."""
    convertible = cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value)
    return float(convertible)


def scalar_int(value: object) -> int:
    """Return a value that the caller has established is an integer scalar."""
    convertible = cast(str | bytes | bytearray | SupportsInt | SupportsIndex, value)
    return int(convertible)
