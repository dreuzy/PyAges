# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file centralizes display names shared by concentration and report plots.

"""Format tracer identifiers consistently across PyAges figures."""

from __future__ import annotations


def pretty_tracer_name(name: str) -> str:
    """Return the conventional display spelling of one tracer identifier."""
    lower = name.lower()
    if lower.startswith("cfc"):
        return name.upper()
    if lower == "sf6":
        return "SF6"
    return name


__all__ = ["pretty_tracer_name"]
