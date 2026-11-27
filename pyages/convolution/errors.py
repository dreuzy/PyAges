# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1
# This file defines the shared failure type for tracer/LPM convolution.
# Grid builders and integrators raise it for invalid numerical inputs or unmet
# accuracy limits, giving callers one explicit error to handle.

"""Exceptions shared by tracer/LPM convolution components."""


class ConvolutionError(Exception):
    """Report a violated numerical contract during preparation or execution."""


__all__ = ["ConvolutionError"]
